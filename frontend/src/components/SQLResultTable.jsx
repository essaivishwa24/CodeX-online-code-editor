function displayCell(value) {
  if (value === null) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function SQLResultTable({ result }) {
  const hasTable = Array.isArray(result.columns) && result.columns.length > 0;
  const elapsed = result.executionTimeMs == null
    ? "Time unavailable"
    : `${result.executionTimeMs.toFixed(1)} ms`;

  return (
    <div className="sql-result" aria-live="polite">
      <div className="sql-result-summary">
        <span>{result.message || "SQL executed successfully."}</span>
        <span>{elapsed}</span>
      </div>
      {hasTable ? (
        <div className="sql-table-scroll">
          <table className="sql-table">
            <thead>
              <tr>
                {result.columns.map((column, index) => (
                  <th key={`${column}-${index}`} scope="col">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows?.length ? result.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {result.columns.map((column, columnIndex) => (
                    <td
                      className={row[columnIndex] === null ? "sql-null" : ""}
                      key={`${column}-${columnIndex}`}
                    >
                      {displayCell(row[columnIndex])}
                    </td>
                  ))}
                </tr>
              )) : (
                <tr>
                  <td className="sql-empty" colSpan={result.columns.length}>Query returned no rows.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="sql-message">No result set was returned.</div>
      )}
    </div>
  );
}
