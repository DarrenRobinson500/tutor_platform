import { useEffect, useState, useRef } from "react";
import { apiFetch, apiFetchJson } from "../../utils/apiFetch"

export function TutorStudentList({ tutorId }: { tutorId: string }) {
  const [students, setStudents] = useState([]);

  useEffect(() => {
    apiFetch(`/api/tutors/${tutorId}/students/`)
      .then(res => res.json())
      .then(data => setStudents(data));
  }, [tutorId]);

  return (
<ul className="list-group mt-3">
  {students.map((s: any) => (
    <li
      key={s.id}
      className="list-group-item d-flex justify-content-between align-items-center"
    >
      <span>{s.first_name} {s.last_name}</span>

      <a
        className="btn btn-outline-primary btn-sm"
        href={`/student/${s.id}`}
      >
        View Student Home Page
      </a>
    </li>
  ))}
</ul>

  );
}