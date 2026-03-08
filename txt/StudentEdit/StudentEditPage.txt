import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch";

export function StudentEditPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();

  // Read returnTo from query string
  const params = new URLSearchParams(window.location.search);
  const returnTo = params.get("returnTo") || `/student/${studentId}`;

  const [yearLevel, setYearLevel] = useState("");
  const [areaOfStudy, setAreaOfStudy] = useState("");
  const [active, setActive] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/api/students/${studentId}/`)
      .then(async (res) => {
        const data = await res.json();
        setYearLevel(data.year_level || "");
        setAreaOfStudy(data.area_of_study || "");
        setActive(data.active);   // NEW
      })
      .finally(() => setLoading(false));
  }, [studentId]);

  const handleSave = async () => {
    await apiFetch(`/api/students/${studentId}/edit/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fields: {
          year_level: yearLevel,
          area_of_study: areaOfStudy,
          active: active,
        },
      }),
    });

    navigate(returnTo);
  };

  if (loading) return <p>Loading…</p>;

  return (
    <div className="container mt-4">
      <h1>Edit Student Details</h1>

      <div className="mb-3">
        <label className="form-label">Year Level</label>
        <input
          type="text"
          className="form-control"
          value={yearLevel}
          onChange={(e) => setYearLevel(e.target.value)}
        />
      </div>

      <div className="mb-3">
        <label className="form-label">Area of Study</label>
        <textarea
          className="form-control"
          value={areaOfStudy}
          onChange={(e) => setAreaOfStudy(e.target.value)}
        />
      </div>

      <div className="form-check mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="activeCheck"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
        />
        <label className="form-check-label" htmlFor="activeCheck">
          Active student
        </label>
      </div>

      <button className="btn btn-primary me-2" onClick={handleSave}>
        Save
      </button>

      <button
        className="btn btn-outline-secondary"
        onClick={() => navigate(returnTo)}
      >
        Cancel
      </button>
    </div>
  );
}