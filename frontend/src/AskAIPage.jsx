import "./AskAIPage.css";

export default function AskAIPage({
  onBack,
  question,
  setQuestion,
  answer,
  sources,
  loading,
  error,
  onAsk,
  machines,
  machinesLoading,
  machineId,
  setMachineId,
}) {
  return (
    <div className="page-content ask-ai-page">
      <button className="page-back-button" onClick={onBack}>
        <span aria-hidden="true">←</span>
        Back to Dashboard
      </button>

      <div className="page-heading">
        <p className="eyebrow">AI MAINTENANCE ASSISTANT</p>
        <h1>Ask AI</h1>
        <p className="page-description">
          Get machine-specific answers from maintenance history and technical
          manuals.
        </p>
      </div>

      <section className="ask-page-card">
        <div className="section-heading">
          <div>
            <h2>What problem are you experiencing?</h2>
            <p>
              Select a machine and describe the problem to search its technical
              documentation.
            </p>
          </div>
          <span className="ai-badge">AI ASSISTED</span>
        </div>

        <form onSubmit={onAsk}>
          <div className="machine-selection">
            <label htmlFor="machine">Select machine</label>
            <select
              id="machine"
              className="dropdown"
              value={machineId}
              onChange={(event) => setMachineId(event.target.value)}
              disabled={machinesLoading}
            >
              <option value="">
                {machinesLoading
                  ? "Loading machines..."
                  : machines.length
                    ? "Choose a machine"
                    : "No machines available"}
              </option>
              {machines.map((machine) => (
                <option key={machine.id} value={String(machine.id)}>
                  {machine.id} : {machine.name} — {machine.machine_type}
                </option>
              ))}
            </select>
          </div>

          <label className="ask-question-label" htmlFor="question">
            Describe the problem
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Example: The conveyor motor is overheating. What should I check in the manual?"
          />

          <button className="ask-button" type="submit" disabled={loading}>
            {loading
              ? "Searching maintenance logs and manuals..."
              : "Ask Maintenance AI →"}
          </button>
        </form>

        {error && <p className="error-message">{error}</p>}

        {answer && (
          <section className="answer-panel">
            <h3>Maintenance assistant response</h3>
            <p className="answer-text">{answer}</p>

            {sources.length > 0 && (
              <div>
                <h4>Sources</h4>
                <ul>
                  {sources.map((source, index) => (
                    <li
                      key={
                        source.source_type === "maintenance_log"
                          ? `log-${source.log_id}`
                          : `manual-${source.filename}-${source.page_number}-${index}`
                      }
                    >
                      {source.source_type === "maintenance_log"
                        ? `Maintenance Log #${source.log_id} — ${source.record_type} · ${source.recorded_on}`
                        : `${source.filename} — Page ${source.page_number}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <p className="disclaimer">
          AI-generated guidance is not a verified repair instruction. Follow
          approved safety procedures and consult a qualified technician.
        </p>
      </section>
    </div>
  );
}
