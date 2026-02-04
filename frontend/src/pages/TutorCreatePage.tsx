import { useState } from "react";
import { Layout } from "./components/Layout";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"


export function TutorCreatePage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<any>(null);

  async function handleSubmit(e: any) {
    e.preventDefault();

    const res = await apiFetch("/api/tutors/create_tutor/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });

    const data = await res.json();
    setResult(data);
  }

  return (
  <Layout>
    <div className="container mt-4">
      <h2>Create New Tutor</h2>

      <form onSubmit={handleSubmit} className="mt-3">

        <div className="mb-3">
          <label className="form-label">Tutor Name</label>
          <input className="form-control"
                 value={name}
                 onChange={e => setName(e.target.value)} />
        </div>

        <div className="mb-3">
          <label className="form-label">Email (username)</label>
          <input className="form-control"
                 value={email}
                 onChange={e => setEmail(e.target.value)} />
        </div>

        <div className="mb-3">
          <label className="form-label">Password (optional)</label>
          <input className="form-control"
                 value={password}
                 onChange={e => setPassword(e.target.value)}
                 placeholder="Leave blank for auto-generated" />
        </div>

        <button className="btn btn-primary">Create Tutor</button>
      </form>

      {result && (
        <div className="alert alert-success mt-4">
          <h5>Tutor Created</h5>
          <p><strong>Name:</strong> {result.name}</p>
          <p><strong>Email:</strong> {result.email}</p>
          {result.password && (
            <p><strong>Password:</strong> {result.password}</p>
          )}
        </div>
      )}
    </div>
</Layout>
    );
}