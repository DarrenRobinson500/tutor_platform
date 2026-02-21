/* eslint-disable react-hooks/exhaustive-deps */
import { useParams, useNavigate } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { Layout } from "./components/Layout";
import { WeekData } from "../types/weekly";
import { apiFetch } from "../utils/apiFetch";

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

// Helper: get Sunday start of week
function getSundayStart(date: Date): string {
  const d = new Date(date);
  const day = d.getDay();
  const sunday = new Date(d);
  sunday.setDate(d.getDate() - day);
  return sunday.toISOString().slice(0, 10);
}

// Round up to nearest buffer increment
function roundUpToBuffer(date: Date, buffer: number) {
  const minutes = date.getMinutes();
  const remainder = minutes % buffer;
  if (remainder === 0) return date;
  return new Date(date.getTime() + (buffer - remainder) * 60000);
}

export function StudentBookingPage() {
  const { id } = useParams();
  const [student, setStudent] = useState<any>(null);
  const [week, setWeek] = useState<WeekData | null>(null);
  const [tutorSettings, setTutorSettings] = useState<any>(null);
  const [manualDate, setManualDate] = useState("");
  const [manualTime, setManualTime] = useState("");
  const [repeatWeekly, setRepeatWeekly] = useState(false);
  const [manualMessage, setManualMessage] = useState("");
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const navigate = useNavigate();
//   const { studentId } = useParams();

  const [slotOptions, setSlotOptions] = useState<{
    date: string;
    blockStart: string;
    blockEnd: string;
    validStarts: string[];
  } | null>(null);

  const [showBookingModal, setShowBookingModal] = useState(false);

  // -----------------------------
  // Manual booking handler
  // -----------------------------
  const handleManualBooking = async () => {
    if (!manualDate || !manualTime) {
      setManualMessage("Please choose a date and time.");
      return;
    }

    setBookingLoading(true); // show spinner

    const payload = {
      student_id: student.id,
      date: manualDate,
      time: manualTime,
      repeat_weekly: repeatWeekly,
    };

    try {
      const res = await apiFetch(`/api/tutors/${tutorId}/check_and_book/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      handleBookingResponse(data);

    } finally {
      setBookingLoading(false); // hide spinner
    }
  };


  // -----------------------------
  // Unified booking response handler
  // -----------------------------
  const handleBookingResponse = (data: any) => {
    const created = data.created || 0;
    const results = data.results || [];
    const failures = results.filter((r: any) => !r.success);

    if (created > 0) {
      if (failures.length === 0) {
        setManualMessage(`Booked ${created} session${created > 1 ? "s" : ""}.`);
      } else {
        const failList = failures
          .map((f: any) => `Week ${f.week}: ${f.reason}`)
          .join(", ");
        setManualMessage(
          `Booked ${created} session${created > 1 ? "s" : ""}, but some weeks failed: ${failList}`
        );
      }
      if (weekStart) {
        loadCalendar(weekStart);
      } else {
        loadCalendar();
      }

    } else {
      if (failures.length > 0) {
        const failList = failures
          .map((f: any) => `Week ${f.week}: ${f.reason}`)
          .join(", ");
        setManualMessage(`No sessions booked. Reasons: ${failList}`);
      } else {
        setManualMessage("No sessions booked.");
      }
    }
  };

  // -----------------------------
  // Load student + tutor settings
  // -----------------------------
  useEffect(() => {
    apiFetch(`/api/students/${id}/home/`)
      .then((res) => res.json())
      .then(async (data) => {
        setStudent(data);

        if (data.tutor_id) {
          const tutorRes = await apiFetch(
            `/api/tutors/${data.tutor_id}/session_settings/`
          );
          const tutorSettings = await tutorRes.json();
          setTutorSettings(tutorSettings);
        }
      });
  }, [id]);

  const tutorId = student?.tutor_id;

  // -----------------------------
  // Load weekly calendar
  // -----------------------------
  useEffect(() => {
    if (tutorId) loadCalendar();
  }, [tutorId]);

  const loadCalendar = async (startOverride?: string) => {
    if (!tutorId) return;

    setLoading(true);   // ⭐ show spinner

    const start = startOverride || getSundayStart(new Date());
    setWeekStart(start);

    const studentId = student?.id;

    const url = studentId
      ? `/api/tutors/${tutorId}/weekly_slots/?week_start=${start}&student=${studentId}`
      : `/api/tutors/${tutorId}/weekly_slots/?week_start=${start}`;

    try {
      const res = await apiFetch(url);
      const data = await res.json();
      setWeek(data.week);
    } finally {
      setLoading(false);  // ⭐ hide spinner
    }
  };

  // -----------------------------
  // Slot selection → show modal
  // -----------------------------
  const handleSelectSlot = (
    day: string,
    blockStart: string,
    blockEnd: string
  ) => {
    const start = new Date(`${day}T${blockStart}:00`);
    const end = new Date(`${day}T${blockEnd}:00`);
    const sessionMinutes = Number(tutorSettings.default_session_minutes);
    const buffer = Number(tutorSettings.buffer_minutes);

    const validStarts: string[] = [];
    let t = roundUpToBuffer(new Date(start), buffer);

    while (t.getTime() + sessionMinutes * 60000 <= end.getTime()) {
      const hours = String(t.getHours()).padStart(2, "0");
      const minutes = String(t.getMinutes()).padStart(2, "0");
      validStarts.push(`${hours}:${minutes}`);
      t = new Date(t.getTime() + buffer * 60000);
    }

    setSlotOptions({
      date: day,
      blockStart,
      blockEnd,
      validStarts,
    });

    setShowBookingModal(true);
  };

  // -----------------------------
  // Book a specific slot
  // -----------------------------
  const handleBook = async (startTime: string) => {
    if (!slotOptions) return;

    setBookingLoading(true);   // ⭐ show spinner

    const payload = {
      student_id: student.id,
      date: slotOptions.date,
      time: startTime,
      repeat_weekly: false,
    };

    try {
      const res = await apiFetch(
        `/api/tutors/${student.tutor_id}/check_and_book/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      const data = await res.json();
      handleBookingResponse(data);
    } finally {
      setBookingLoading(false);  // ⭐ hide spinner
      setShowBookingModal(false);
      setSlotOptions(null);
    }
  };


  // -----------------------------
  // Delete booking
  // -----------------------------
  const handleDeleteBooking = async (bookingId: number) => {
    await apiFetch(`/api/tutors/${tutorId}/delete_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: bookingId }),
    });

    loadCalendar();
  };

  // -----------------------------
  // UI
  // -----------------------------
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
        <h1>Booking for: {student.name}</h1>
        <p><strong>Email:</strong> {student.email}<br/>
        <strong>Year Level:</strong> {student.year_level || "Not set"}<br/>
        <strong>Area of Study:</strong> {student.area_of_study || "Not set"}
        </p>
        <button
          className="btn btn-outline-primary"
          onClick={() => navigate(`/students/${id}/edit`)}
        >
          Edit My Details
        </button>


        {/* ⭐ Message banner */}
        {manualMessage && (
          <div className="alert alert-info mt-3">{manualMessage}</div>
        )}

        {bookingLoading && (
          <div className="text-center my-3">
            <div className="spinner-border text-success" role="status">
              <span className="visually-hidden">Booking session…</span>
            </div>
            <div style={{ marginTop: "0.5rem", fontWeight: 500 }}>
              Booking session…
            </div>
          </div>
        )}

        {/* Manual booking */}
        <div className="manual-booking d-flex align-items-end gap-3 mt-4 p-3 border rounded">
          <div>
            <label>Date</label>
            <input
              type="date"
              className="form-control"
              value={manualDate}
              onChange={(e) => setManualDate(e.target.value)}
            />
          </div>

          <div>
            <label>Start time</label>
            <input
              type="time"
              className="form-control"
              value={manualTime}
              onChange={(e) => setManualTime(e.target.value)}
            />
          </div>

          <div className="form-check mb-2">
            <input
              type="checkbox"
              className="form-check-input"
              id="repeatWeekly"
              checked={repeatWeekly}
              onChange={(e) => setRepeatWeekly(e.target.checked)}
            />
            <label htmlFor="repeatWeekly" className="form-check-label">
              Every week
            </label>
          </div>

        <button
          className="btn btn-outline-primary"
          onClick={handleManualBooking}
          disabled={bookingLoading}
        >
          {bookingLoading ? "Booking…" : "Book Session"}
        </button>

        </div>

        <br />

        <div style={{ marginBottom: "1.5rem", fontSize: "1.4rem", fontWeight: 600 }}>
          {student?.tutor_name
            ? `${student.tutor_name}'s Calendar`
            : "Tutor's Calendar"}
        </div>

        {/* Week navigation */}
        <div className="d-flex align-items-center gap-3 mb-3">
          <button
            className="btn btn-outline-primary"
            onClick={() => loadCalendar(getSundayStart(new Date(new Date(weekStart!).setDate(new Date(weekStart!).getDate() - 7))))}
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
            onClick={() => loadCalendar(getSundayStart(new Date(new Date(weekStart!).setDate(new Date(weekStart!).getDate() + 7))))}
          >
            Next Week →
          </button>
        </div>

        {loading && (
          <div className="text-center my-3">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading…</span>
            </div>
          </div>
        )}

        {/* Calendar */}
        <div style={{ opacity: loading ? 0.4 : 1, pointerEvents: loading ? "none" : "auto" }}>
          {week && (
            <WeeklyCalendar
              week={week}
              mode="student"
              onSelectSlot={handleSelectSlot}
              onDeleteBooking={handleDeleteBooking}
            />
          )}
        </div>


        {/* Booking modal */}
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
              boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
            }}
          >
            <h3>Select a start time</h3>

            {slotOptions.validStarts.length === 0 && (
              <p>No valid start times available in this block.</p>
            )}

            {slotOptions.validStarts.map((t) => (
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