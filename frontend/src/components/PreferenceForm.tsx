import { useState } from "react";

const MOODS = ["Light & fun", "Intense & gripping", "Scary", "Romantic", "Other"];
const LANGUAGES = ["Hindi", "English", "Tamil", "Telugu", "Kannada", "Any"];
const CONTENT_TYPES = ["Movies only", "Include series"];
const RATINGS = [6, 7, 8, 9];
const ERAS = ["Any", "Classic (pre-2000)", "2000–2020", "Recent (2021–2026)"];

export interface PreferenceFormValues {
  moods: string[];
  mood_text: string;
  languages: string[];
  content_type: string;
  min_rating: number;
  eras: string[];
}

interface Props {
  onSubmit: (values: PreferenceFormValues) => void | Promise<void>;
  submitting?: boolean;
}

function toggleExclusive(current: string[], value: string, exclusiveValue: string): string[] {
  if (value === exclusiveValue) {
    return current.includes(value) ? [] : [exclusiveValue];
  }
  const withoutExclusive = current.filter((v) => v !== exclusiveValue);
  if (withoutExclusive.includes(value)) {
    return withoutExclusive.filter((v) => v !== value);
  }
  return [...withoutExclusive, value];
}

function toggleSimple(current: string[], value: string): string[] {
  return current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value];
}

export default function PreferenceForm({ onSubmit, submitting }: Props) {
  const [moods, setMoods] = useState<string[]>([]);
  const [moodText, setMoodText] = useState("");
  const [languages, setLanguages] = useState<string[]>([]);
  const [contentType, setContentType] = useState(CONTENT_TYPES[0]);
  const [minRating, setMinRating] = useState(6);
  const [eras, setEras] = useState<string[]>([]);

  const canSubmit = moods.length > 0 && languages.length > 0 && eras.length > 0;

  return (
    <div>
      <label className="field-label">What's the mood tonight?</label>
      <div className="chip-group">
        {MOODS.map((m) => (
          <div
            key={m}
            className={`chip ${moods.includes(m) ? "selected" : ""}`}
            onClick={() => setMoods(toggleSimple(moods, m))}
          >
            {m}
          </div>
        ))}
      </div>

      <label className="field-label">Describe what you're in the mood for (optional)</label>
      <textarea
        placeholder="e.g. something that doesn't require too much brainpower after a long week..."
        value={moodText}
        onChange={(e) => setMoodText(e.target.value)}
      />

      <label className="field-label">Language</label>
      <div className="chip-group">
        {LANGUAGES.map((l) => (
          <div
            key={l}
            className={`chip ${languages.includes(l) ? "selected" : ""}`}
            onClick={() => setLanguages(toggleExclusive(languages, l, "Any"))}
          >
            {l}
          </div>
        ))}
      </div>

      <label className="field-label">Content type</label>
      <div className="chip-group">
        {CONTENT_TYPES.map((c) => (
          <div
            key={c}
            className={`chip ${contentType === c ? "selected" : ""}`}
            onClick={() => setContentType(c)}
          >
            {c}
          </div>
        ))}
      </div>

      <label className="field-label">Minimum IMDb rating</label>
      <div className="chip-group">
        {RATINGS.map((r) => (
          <div
            key={r}
            className={`chip ${minRating === r ? "selected" : ""}`}
            onClick={() => setMinRating(r)}
          >
            {r}+{r === 9 && <span className="caveat">very few titles</span>}
          </div>
        ))}
      </div>

      <label className="field-label">Era</label>
      <div className="chip-group">
        {ERAS.map((e) => (
          <div
            key={e}
            className={`chip ${eras.includes(e) ? "selected" : ""}`}
            onClick={() => setEras(toggleExclusive(eras, e, "Any"))}
          >
            {e}
          </div>
        ))}
      </div>

      <button
        className="btn-primary"
        style={{ width: "100%", marginTop: 12 }}
        disabled={!canSubmit || submitting}
        onClick={() =>
          onSubmit({
            moods,
            mood_text: moodText,
            languages,
            content_type: contentType,
            min_rating: minRating,
            eras,
          })
        }
      >
        {submitting ? "Submitting..." : "Submit preferences"}
      </button>
    </div>
  );
}
