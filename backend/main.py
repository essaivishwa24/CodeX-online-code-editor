"""CodeX API: auth, SQL-backed projects/files, sharing, ZIP export and execution."""
import io, re, os, secrets, zipfile, sys
from contextlib import asynccontextmanager
from pathlib import PurePath
from pathlib import Path
if not __package__:
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path: sys.path.insert(0, root)
from fastapi import FastAPI, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
if __package__:
    from .database import get_db, init_db
    from .db_models import User, Project, ProjectFile, ProjectVersion, Execution
    from .auth import current_user, admin_user, hash_password, verify_password, create_token
    from .routes.health import router as health_router
    from .routes.code_runner import log_runtime_diagnostics, router as code_runner_router
else:
    from backend.database import get_db, init_db
    from backend.db_models import User, Project, ProjectFile, ProjectVersion, Execution
    from backend.auth import current_user, admin_user, hash_password, verify_password, create_token
    from backend.routes.health import router as health_router
    from backend.routes.code_runner import log_runtime_diagnostics, router as code_runner_router

class Register(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    email: EmailStr
    password: SecretStr
    confirm_password: SecretStr | None = None
    @field_validator("password")
    @classmethod
    def password_is_valid(cls, value):
        raw = value.get_secret_value()
        if len(raw) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(raw) > 128:
            raise ValueError("Password must not exceed 128 characters")
        if len(raw.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed the bcrypt limit")
        return value

    @field_validator("confirm_password")
    @classmethod
    def match(cls, v, info):
        password = info.data.get("password")
        if v is not None and password is not None and password.get_secret_value() != v.get_secret_value():
            raise ValueError("Passwords do not match")
        return v

class Login(BaseModel):
    email: EmailStr
    password: SecretStr

class PublicUser(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: PublicUser
class ProjectIn(BaseModel): name: str = Field(min_length=1, max_length=120); primary_language: str = "python"; description: str = ""; template: str = "basic"
class FileIn(BaseModel): filename: str = Field(min_length=1, max_length=255); language: str; content: str = ""
class FileUpdate(BaseModel):
    content: str = Field(max_length=1_000_000)
    filename: str | None = None
    language: str | None = None


PROJECT_TEMPLATES = {
    "python": ("main.py", 'print("Hello from CodeX")'),
    "javascript": ("main.js", 'console.log("Hello from CodeX");'),
    "typescript": ("main.ts", 'const message: string = "Hello from CodeX";\nconsole.log(message);'),
    "java": ("Main.java", 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello from CodeX");\n    }\n}'),
    "c": ("main.c", '#include <stdio.h>\n\nint main() {\n    printf("Hello from CodeX\\n");\n    return 0;\n}'),
    "cpp": ("main.cpp", '#include <iostream>\n\nint main() {\n    std::cout << "Hello from CodeX" << std::endl;\n    return 0;\n}'),
    "sql": ("query.sql", "CREATE TABLE users (\n    id INTEGER PRIMARY KEY,\n    name TEXT NOT NULL\n);\n\nINSERT INTO users (name) VALUES ('Ada'), ('Grace');\n\nSELECT * FROM users ORDER BY id;"),
    "html": ("index.html", '<!DOCTYPE html>\n<html>\n<head>\n    <title>CodeX</title>\n</head>\n<body>\n    <h1>Hello from CodeX</h1>\n</body>\n</html>'),
    "css": ("style.css", 'body {\n    font-family: Arial, sans-serif;\n}\n\nh1 {\n    color: blue;\n}'),
}

def clean_filename(name):
    if not name or name != PurePath(name).name or name in {".", ".."} or "/" in name or "\\" in name: raise HTTPException(400, "Invalid filename")
    if not re.fullmatch(r"[A-Za-z0-9._ -]+", name): raise HTTPException(400, "Invalid filename")
    return name
def project_for(db, user, project_id):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not project: raise HTTPException(404, "Project not found")
    return project
def project_json(p):
    return {"id":p.id,"name":p.name,"description":p.description,"primary_language":p.primary_language,"is_favorite":p.is_favorite,"is_public":p.is_public,"share_token":p.share_token,"created_at":p.created_at,"updated_at":p.updated_at,"files":[{"id":f.id,"filename":f.filename,"language":f.language,"content":f.content,"updated_at":f.updated_at} for f in p.files]}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_runtime_diagnostics()
    yield

def create_app():
    init_db(); app=FastAPI(title="CodeX API", version="2.0.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc):
        # FastAPI's default validation payload includes the rejected input. Never
        # return password values, even when a password validation rule fails.
        errors = []
        for error in exc.errors():
            location = error.get("loc", ())
            safe_error = {key: error[key] for key in ("type", "loc", "msg") if key in error}
            if not any(part in {"password", "confirm_password"} for part in location):
                safe_error["input"] = error.get("input")
            errors.append(safe_error)
        return JSONResponse(status_code=422, content={"detail": errors})

    required_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://code-x-online-code-editor.vercel.app",
    ]
    configured_origins = [x.strip().rstrip("/") for x in os.environ.get("CODEX_CORS_ORIGINS", "").split(",") if x.strip()]
    origins = list(dict.fromkeys(required_origins + configured_origins))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"^https://code-x-online-code-editor-[a-zA-Z0-9-]+-essai-vishwa\.vercel\.app$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router,prefix="/api"); app.include_router(code_runner_router,prefix="/api")
    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(data:Register, db:Session=Depends(get_db)):
        normalized_email = data.email.lower()
        if db.scalar(select(User).where(User.email == normalized_email)):
            raise HTTPException(409, "Unable to create account with those details")
        if db.scalar(select(User).where(User.username == data.username)):
            raise HTTPException(409, "Unable to create account with those details")
        user=User(username=data.username,email=normalized_email,password_hash=hash_password(data.password.get_secret_value())); db.add(user); db.commit(); db.refresh(user)
        return {"access_token":create_token(user),"token_type":"bearer","user":{"id":user.id,"username":user.username,"email":user.email,"role":user.role}}
    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(data:Login, db:Session=Depends(get_db)):
        user=db.scalar(select(User).where(User.email==data.email.lower()))
        if not user or not verify_password(data.password.get_secret_value(),user.password_hash) or not user.is_active:
            raise HTTPException(401,"Invalid email or password")
        return {"access_token":create_token(user),"token_type":"bearer","user":{"id":user.id,"username":user.username,"email":user.email,"role":user.role}}
    @app.get("/api/auth/me", response_model=PublicUser)
    def me(user:User=Depends(current_user)): return {"id":user.id,"username":user.username,"email":user.email,"role":user.role}
    @app.post("/api/auth/logout")
    def logout(user: User = Depends(current_user)): return {"ok":True}
    @app.get("/api/projects")
    def projects(user:User=Depends(current_user),db:Session=Depends(get_db)): return [project_json(p) for p in db.scalars(select(Project).where(Project.user_id==user.id).order_by(Project.updated_at.desc())).all()]
    @app.post("/api/projects")
    def new_project(data:ProjectIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
        p=Project(user_id=user.id,name=data.name.strip(),description=data.description,primary_language=data.primary_language); db.add(p); db.flush()
        name,content=PROJECT_TEMPLATES.get(data.primary_language,("main.txt","# Start building with CodeX")); db.add(ProjectFile(project_id=p.id,filename=name,language=data.primary_language,content=content)); db.commit(); db.refresh(p); return project_json(p)
    @app.get("/api/projects/{project_id}")
    def get_project(project_id:int,user=Depends(current_user),db:Session=Depends(get_db)): return project_json(project_for(db,user,project_id))
    @app.patch("/api/projects/{project_id}")
    def update_project(project_id:int,data:dict,user=Depends(current_user),db:Session=Depends(get_db)):
        p=project_for(db,user,project_id)
        for key in ("name","description","is_favorite","is_public"):
            if key in data: setattr(p,key,data[key])
        if "is_public" in data: p.share_token = (p.share_token or secrets.token_urlsafe(32)) if data["is_public"] else None
        db.commit(); db.refresh(p); return project_json(p)
    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id:int,user=Depends(current_user),db:Session=Depends(get_db)): db.delete(project_for(db,user,project_id)); db.commit(); return {"ok":True}
    @app.post("/api/projects/{project_id}/duplicate")
    def duplicate(project_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
        src=project_for(db,user,project_id); p=Project(user_id=user.id,name=f"{src.name} copy",description=src.description,primary_language=src.primary_language); db.add(p); db.flush()
        for f in src.files: db.add(ProjectFile(project_id=p.id,filename=f.filename,language=f.language,content=f.content))
        db.commit(); db.refresh(p); return project_json(p)
    @app.post("/api/projects/{project_id}/files")
    def add_file(project_id:int,data:FileIn,user=Depends(current_user),db:Session=Depends(get_db)):
        p=project_for(db,user,project_id); clean_filename(data.filename)
        if db.scalar(select(ProjectFile).where(ProjectFile.project_id==p.id,ProjectFile.filename==data.filename)): raise HTTPException(409,"File already exists")
        f=ProjectFile(project_id=p.id,filename=data.filename,language=data.language,content=data.content); db.add(f); db.commit(); db.refresh(f); return {"id":f.id,"filename":f.filename,"language":f.language,"content":f.content}
    @app.patch("/api/projects/{project_id}/files/{file_id}")
    def edit_file(project_id:int,file_id:int,data:FileUpdate,user=Depends(current_user),db:Session=Depends(get_db)):
        p=project_for(db,user,project_id); f=db.scalar(select(ProjectFile).where(ProjectFile.id==file_id,ProjectFile.project_id==p.id))
        if not f: raise HTTPException(404,"File not found")
        if data.filename: clean_filename(data.filename); f.filename=data.filename
        if data.language: f.language=data.language
        f.content=data.content; latest=(db.scalar(select(func.max(ProjectVersion.version_number)).where(ProjectVersion.file_id==f.id)) or 0)+1; db.add(ProjectVersion(project_id=p.id,file_id=f.id,content=f.content,version_number=latest)); db.commit(); return {"ok":True,"version":latest}
    @app.delete("/api/projects/{project_id}/files/{file_id}")
    def remove_file(project_id:int,file_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
        p=project_for(db,user,project_id); f=db.scalar(select(ProjectFile).where(ProjectFile.id==file_id,ProjectFile.project_id==p.id))
        if not f: raise HTTPException(404,"File not found")
        db.delete(f); db.commit(); return {"ok":True}
    @app.get("/api/share/{token}")
    def shared(token:str,db:Session=Depends(get_db)):
        p=db.scalar(select(Project).where(Project.share_token==token,Project.is_public==True))
        if not p: raise HTTPException(404,"Shared project not found")
        return project_json(p)
    @app.get("/api/projects/{project_id}/download")
    def download(project_id:int,user=Depends(current_user),db:Session=Depends(get_db)):
        p=project_for(db,user,project_id); stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as z:
            for f in p.files: z.writestr(f.filename,f.content)
        stream.seek(0); return StreamingResponse(stream,media_type="application/zip",headers={"Content-Disposition":f'attachment; filename="{p.name}.zip"'})
    @app.get("/api/admin/stats")
    def stats(user=Depends(admin_user),db:Session=Depends(get_db)): return {"total_users":db.scalar(select(func.count(User.id))),"active_users":db.scalar(select(func.count(User.id)).where(User.is_active==True)),"total_projects":db.scalar(select(func.count(Project.id))),"executions":db.scalar(select(func.count(Execution.id)))}
    return app
app=create_app()
