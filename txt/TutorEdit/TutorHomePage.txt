/* eslint-disable react-hooks/exhaustive-deps */

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Layout } from "./components/Layout";
import { TutorStudentList } from "./components/TutorStudentList";
// import { TutorTemplateList } from "./components/TutorTemplateList";
import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { WeekData } from "../types/weekly";
import { apiFetch } from "../utils/apiFetch"

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

//   const loadCalendar = async (startOverride?: string) => {
//     const start = startOverride || getSundayStart(new Date());
//     setWeekStart(start);
//
//     const res = await apiFetch(
//       `/api/tutors/${id}/weekly_slots/?week_start=${start}&tutor_view=true`
//     );
//
//     const data = await res.json();
//     setWeek(data.week);
//   };

// eslint-disable-next-line react-hooks/exhaustive-deps
// useEffect(() => {
//   loadCalendar();
// }, []);


//   function addDays(dateString: string, days: number): string {
//     const d = new Date(dateString);
//     d.setDate(d.getDate() + days);
//     return d.toISOString().slice(0, 10);
//   }

//   const handleDeleteBooking = async (bookingId: number) => {
//     await apiFetch(`/api/tutors/${id}/delete_booking/`, {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ booking_id: bookingId })
//     });
//
//     loadCalendar();
//   };

  if (!tutor) return <div className="container mt-4">Loading…</div>;

  return (
  <Layout>
    <div className="container mt-4">
      <h2>{tutor.name}</h2>
      <p>Email: {tutor.email}</p>

      <hr />

      <h4 className="mt-4">Students</h4>
      <div className="d-flex justify-content-between align-items-center mb-3">
          <a className="btn btn-outline-primary btn-sm" href={`/admin/students/new?tutor=${id}`}>
            + New Student
          </a>
        </div>

      <TutorStudentList tutorId={id!} />

      <hr />


        {/* RIGHT SIDE — Adjust Weekly Schedule */}



    </div>


  </Layout>

  );
}