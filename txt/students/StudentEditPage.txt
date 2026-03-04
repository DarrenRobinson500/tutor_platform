import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch";

export function StudentEditPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();

  const [yearLevel, setYearLevel] = useState("");
  const [areaOfStudy, setAreaOfStudy] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/api/students/${studentId}/`)
      .then(async (res) => {
        const data = await res.json();
        setYearLevel(data.year_level || "");
        setAreaOfStudy(data.area_of_study || "");
      })
      .finally(() => setLoading(false));
  }, [studentId]);

  const handleSave = async () => {
    await apiFetch(`/api/students/${studentId}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        year_level: yearLevel,
        area_of_study: areaOfStudy,
      }),
    });

    navigate(`/student/${studentId}`);
  };


  if (loading) return <p>Loading…</p>;

  return (
    <div className="container mt-4">
    <h1>{studentId} - Edit Details</h1>

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

      <button className="btn btn-primary me-2" onClick={handleSave}>
        Save
      </button>

      <button
        className="btn btn-outline-secondary"
        onClick={() => navigate(`/student/${studentId}`)}
      >
        Cancel
      </button>
    </div>
  );
}