import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"


export function StudentListPage() {
  const [students, setStudents] = useState([]);

  useEffect(() => {
    apiFetch("/api/students/")
      .then(res => res.json())
      .then(data => setStudents(data));
  }, []);

  return (
    <Layout>
    <div className="container mt-4">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h2>Students</h2>
    </div>

      <ul className="list-group">
        {students.map((s: any) => (
          <li key={s.id} className="list-group-item d-flex justify-content-between">
            <span>{s.first_name} {s.last_name}</span>
            <a className="btn btn-outline-primary btn-sm" href={`/student/${s.id}`}>
              View Student Home
            </a>
          </li>
        ))}
      </ul>
    </div>
    </Layout>
  );
}