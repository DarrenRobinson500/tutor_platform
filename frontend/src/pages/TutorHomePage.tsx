import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Layout } from "./components/Layout";
import { TutorStudentList } from "./components/TutorStudentList";
import { TutorTemplateList } from "./components/TutorTemplateList";
import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { WeekData } from "../types/weekly";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"

function getSundayStart(date: Date): string {
  const d = new Date(date);
  const day = d.getDay(); // Sunday=0
  const sunday = new Date(d);
  sunday.setDate(d.getDate() - day);
  return sunday.toISOString().slice(0, 10);
}

export function TutorHomePage() {
  const { id } = useParams();
  const [tutor, setTutor] = useState<any>(null);
  const [week, setWeek] = useState<WeekData | null>(null);
  const [weekStart, setWeekStart] = useState<string | null>(null);

useEffect(() => {
  apiFetch(`/api/tutors/${id}/home/`)
    .then(res => res.json())
    .then(data => setTutor(data))
    .catch(err => {
      console.error("Failed to load tutor home:", err);
      setTutor(null);
    });
}, [id]);


  useEffect(() => {
    loadCalendar();
  }, []);

  const loadCalendar = async (startOverride?: string) => {
    const start = startOverride || getSundayStart(new Date());
    setWeekStart(start);

    const res = await apiFetch(
      `/api/tutors/${id}/weekly_slots/?week_start=${start}&tutor_view=true`
    );

    const data = await res.json();
    setWeek(data.week);
  };

  function addDays(dateString: string, days: number): string {
    const d = new Date(dateString);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }

  const handleDeleteBooking = async (bookingId: number) => {
    await apiFetch(`/api/tutors/${id}/delete_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: bookingId })
    });

    loadCalendar();
  };

  if (!tutor) return <div className="container mt-4">Loading…</div>;

  return (
  <Layout>
    <div className="container mt-4">
      <h2>{tutor.name}</h2>
      <p>{tutor.email}</p>

      <hr />

      <h4 className="mt-4">Students</h4>
      <div className="d-flex justify-content-between align-items-center mb-3">
          <a className="btn btn-outline-primary btn-sm" href={`/admin/students/new?tutor=${id}`}>
            + New Student
          </a>
        </div>

      <TutorStudentList tutorId={id!} />

      <hr />

      <h4 className="mt-4">Calendar</h4>

      <div className="d-flex justify-content-between align-items-center mb-3">

        {/* LEFT SIDE — week navigation */}
        <div className="d-flex align-items-center gap-3">
          <button
            className="btn btn-outline-primary"
            onClick={() => loadCalendar(addDays(weekStart!, -7))}
          >
            ← Previous Week
          </button>

          <button
            className="btn btn-outline-primary"
            onClick={() => loadCalendar(getSundayStart(new Date()))}
          >
            Jump to Today
          </button>

          <button
            className="btn btn-outline-primary"
            onClick={() => loadCalendar(addDays(weekStart!, +7))}
          >
            Next Week →
          </button>

          <select
            className="form-select custom-blue"
            style={{ width: "180px" }}
            onChange={e => {
              const [year, month] = e.target.value.split("-").map(Number);
              const firstOfMonth = new Date(`${year}-${String(month).padStart(2, "0")}-01`);
              loadCalendar(getSundayStart(firstOfMonth));
            }}
          >
            <option value="">Jump to month…</option>
            {Array.from({ length: 12 }).map((_, i) => {
              const d = new Date();
              const year = d.getFullYear();
              const month = i + 1;
              return (
                <option key={i} value={`${year}-${String(month).padStart(2, "0")}`}>
                  {new Date(year, i).toLocaleString("en-AU", { month: "long", year: "numeric" })}
                </option>
              );
            })}
          </select>
        </div>

        {/* RIGHT SIDE — Adjust Weekly Schedule */}
        <a className="btn btn-outline-primary" href={`/tutor/${id}/schedule`}>
          Add Weekly Availability and Block out Days
        </a>

      </div>

      {week && (
        <WeeklyCalendar
          week={week}
          mode="tutor-schedule"
          showAllBookingLabels={true}
          onDeleteBooking={handleDeleteBooking}
        />
      )}

    </div>


  </Layout>

  );
}