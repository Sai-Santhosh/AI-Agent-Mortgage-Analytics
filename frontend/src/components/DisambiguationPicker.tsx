import './DisambiguationPicker.css'

type Choice = { dataset_id: string; label: string; why: string }

type Props = {
  choices: Choice[]
  onSelect: (datasetId: string) => void
  onCancel: () => void
}

export function DisambiguationPicker({ choices, onSelect, onCancel }: Props) {
  return (
    <div className="disambiguation-panel">
      <p className="disambiguation-title">Which data source should I use?</p>
      <div className="disambiguation-choices">
        {choices.map((c) => (
          <button
            key={c.dataset_id}
            className="choice-btn"
            onClick={() => onSelect(c.dataset_id)}
          >
            <span className="choice-label">{c.label}</span>
            <span className="choice-why">{c.why}</span>
          </button>
        ))}
      </div>
      <button className="cancel-btn" onClick={onCancel}>Cancel</button>
    </div>
  )
}
