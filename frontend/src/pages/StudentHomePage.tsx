import { useParams } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { Layout } from "./components/Layout";
import { WeekData } from "../types/weekly";
import { apiFetch, apiFetchJson } from "../utils/apiFetch"


export interface Segment {
  time: string;
  type: string;
  bookingId?: number;
}

export interface AvailabilityWindow {
  start: string;
  end: string;
}

export interface Booking {
  start: string;
  end: string;
  student: number;
}

export interface DayData {
  date: string;
  availability: AvailabilityWindow[];
  blocked: boolean;
  bookings: Booking[];
  bookable_slots: string[];
  segments: Segment[];
}


// Helper: get Monday in YYYY-MM-DD format
function getSundayStart(date: Date): string {
  const d = new Date(date);
  const day = d.getDay(); // Sunday=0 ... Saturday=6
  const sunday = new Date(d);
  sunday.setDate(d.getDate() - day);
  return sunday.toISOString().slice(0, 10);
}


// ⭐ Round up to nearest buffer increment
function roundUpToBuffer(date: Date, buffer: number) {
  const minutes = date.getMinutes();
  const remainder = minutes % buffer;
  if (remainder === 0) return date;
  return new Date(date.getTime() + (buffer - remainder) * 60000);
}

export function StudentHomePage() {
  const { id } = useParams();
  const [student, setStudent] = useState<any>(null);

  const [showCalendar, setShowCalendar] = useState(false);
  const [week, setWeek] = useState<WeekData | null>(null);
  const [tutorSettings, setTutorSettings] = useState<any>(null);
  const [manualDate, setManualDate] = useState("");
  const [manualTime, setManualTime] = useState("");
  const [repeatWeekly, setRepeatWeekly] = useState(false);
  const [manualMessage, setManualMessage] = useState("");
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [slotOptions, setSlotOptions] = useState<{
    date: string;
    blockStart: string;
    blockEnd: string;
    validStarts: string[];
  } | null>(null);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const handleManualBooking = async () => {
    if (!manualDate || !manualTime) {
      setManualMessage("Please choose a date and time.");
      return;
    }

  const payload = {
    student_id: student.id,
    date: manualDate,
    time: manualTime,
    repeat_weekly: repeatWeekly
  };

  const res = await apiFetch(`/api/tutors/${tutorId}/check_and_book/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();

  setManualMessage(data.message);

  if (data.status === "ok") {
    loadCalendar();
  }
  };

  // Load student
  useEffect(() => {
    apiFetch(`/api/students/${id}/home/`)
      .then(res => res.json())
      .then(async data => {
        console.log("Loaded student:", data);
        setStudent(data);

        // ⭐ Fetch tutor settings
        if (data.tutor_id) {
          const tutorRes = await apiFetch(`/api/tutors/${data.tutor_id}/session_settings/`);
          const tutorSettings = await tutorRes.json();
          console.log("Loaded tutor settings:", tutorSettings);

          setTutorSettings(tutorSettings);
        }
      });
  }, [id]);

  const tutorId = student?.tutor_id;

  useEffect(() => {
    if (tutorId) {
      loadCalendar();
    }
  }, [tutorId]);

  // Load weekly calendar
  const loadCalendar = async (startOverride?: string) => {
    if (!tutorId) return;

    const start = startOverride || getSundayStart(new Date());
    setWeekStart(start);

    const studentId = student?.id;

    const url = studentId
        ? `/api/tutors/${tutorId}/weekly_slots/?week_start=${start}&student=${studentId}`
        : `/api/tutors/${tutorId}/weekly_slots/?week_start=${start}`;

    const res = await apiFetch(url);
    const data = await res.json();

    setWeek(data.week);
    setShowCalendar(true);
  };

  function addDays(dateString: string, days: number): string {
    const d = new Date(dateString);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }

  const handleSelectSlot = (day: string, blockStart: string, blockEnd: string) => {
    const start = new Date(`${day}T${blockStart}:00`);
    const end = new Date(`${day}T${blockEnd}:00`);
    const sessionMinutes = Number(tutorSettings.default_session_minutes);
    const buffer = Number(tutorSettings.buffer_minutes);
    const validStarts: string[] = [];
    let t = roundUpToBuffer(new Date(start), buffer);
    while (t.getTime() + sessionMinutes * 60000 <= end.getTime()) {
      const hours = String(t.getHours()).padStart(2, "0");
      const minutes = String(t.getMinutes()).padStart(2, "0");
      validStarts.push(`${hours}:${minutes}`);   // "HH:MM" in local time
      t = new Date(t.getTime() + buffer * 60000);
    }
    setSlotOptions({
      date: day,
      blockStart,
      blockEnd,
      validStarts
    });
    setShowBookingModal(true);
  };

  // Student chooses a specific start time
  const handleBook = async (startTime: string) => {
    if (!slotOptions) return;

    const payload = {
      student_id: student.id,
      date: slotOptions.date,
      time: startTime,
      repeat_weekly: false
    };

    const res = await apiFetch(`/api/tutors/${student.tutor_id}/check_and_book/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (data.status === "ok") {
      setShowBookingModal(false);
      setSlotOptions(null);
      loadCalendar();
    }
  };

  const handleDeleteBooking = async (bookingId: number) => {
    await apiFetch(`/api/tutors/${tutorId}/delete_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: bookingId })
    });

    loadCalendar();
  };


  if (!student) {
    return (
      <Layout>
        <div className="container mt-4">Loading…</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="container mt-4">
        <h1>Welcome back {student.name} ({student.id})</h1>

        <h2>Tutor ID: {tutorId}</h2>
        <p>{student.email}</p>

        <div className="manual-booking d-flex align-items-end gap-3 mt-4 p-3 border rounded">
          <div>
            <label>Date</label>
            <input
              type="date"
              className="form-control"
              value={manualDate}
              onChange={e => setManualDate(e.target.value)}
            />
          </div>

          <div>
            <label>Start time</label>
            <input
              type="time"
              className="form-control"
              value={manualTime}
              onChange={e => setManualTime(e.target.value)}
            />
          </div>

          <div className="form-check mb-2">
            <input
              type="checkbox"
              className="form-check-input"
              id="repeatWeekly"
              checked={repeatWeekly}
              onChange={e => setRepeatWeekly(e.target.checked)}
            />
            <label htmlFor="repeatWeekly" className="form-check-label">
              Every week
            </label>
          </div>

          <button
            className="btn btn-outline-primary"
            onClick={handleManualBooking}
          >
            Book Session
          </button>
        </div>
        <br/>
        <div style={{ marginBottom: "1.5rem", fontSize: "1.4rem", fontWeight: 600 }}>
          {student?.tutor_name
            ? `${student.tutor_name}'s Calendar`
            : "Tutor's Calendar"}
        </div>

        <div className="d-flex align-items-center gap-3 mb-3">
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


        {week && (
          <WeeklyCalendar
            week={week}
            mode="student"
            onSelectSlot={handleSelectSlot}
            onDeleteBooking={handleDeleteBooking}
          />
        )}


        {/* Debug log */}

        {showBookingModal && slotOptions && tutorSettings && (
          <div
            className="booking-modal"
            style={{
              position: "fixed",
              top: "20%",
              left: "50%",
              transform: "translateX(-50%)",
              background: "white",
              padding: "20px",
              border: "1px solid #ccc",
              zIndex: 9999,
              boxShadow: "0 4px 20px rgba(0,0,0,0.2)"
            }}
          >
            <h3>Select a start time</h3>

            {slotOptions.validStarts.length === 0 && (
              <p>No valid start times available in this block.</p>
            )}

            {slotOptions.validStarts.map(t => (
              <button
                key={t}
                className="btn btn-primary m-1"
                onClick={() => handleBook(t)}
              >
                {t}
              </button>
            ))}

            <button
              className="btn btn-secondary mt-3"
              onClick={() => setShowBookingModal(false)}
            >
              Cancel
            </button>
          </div>
        )}

        <hr />
      </div>
    </Layout>
  );
}