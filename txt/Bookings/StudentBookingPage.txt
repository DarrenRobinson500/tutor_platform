import { useParams } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { WeeklyCalendar } from "./components/WeeklyCalendar";
import { Layout } from "./components/Layout";
import { WeekData } from "../types/weekly";
import { apiFetch } from "../utils/apiFetch";
import { WeeklyBookingCalendar } from "./components/WeeklyBookingCalendar";

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
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [weeklyAvailability, setWeeklyAvailability] = useState<any>(null);


  // Left (weekly) state
  const [weeklyMessage, setWeeklyMessage] = useState("");
  const [weeklyBookingLoading, setWeeklyBookingLoading] = useState(false);
  const [weeklySlotOptions, setWeeklySlotOptions] = useState<{
    date: string;
    weekday: number;
    blockStart: string;
    blockEnd: string;
    validStarts: string[];
  } | null>(null);
  const [showWeeklyModal, setShowWeeklyModal] = useState(false);

  // Right (ad hoc) state
  const [manualDate, setManualDate] = useState("");
  const [manualTime, setManualTime] = useState("");
  const [adHocMessage, setAdHocMessage] = useState("");
  const [adHocBookingLoading, setAdHocBookingLoading] = useState(false);

  const tutorId = student?.tutor_id;

  // -----------------------------
  // Load student and tutor settings and weekly availability
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

  useEffect(() => {
  if (!student) return;

  async function loadWeeklyAvailability() {
    const res = await apiFetch(`/api/students/${student.id}/weekly_availability/`);
    const data = await res.json();
    setWeeklyAvailability(data);
  }

  loadWeeklyAvailability();
}, [student]);


  // -----------------------------
  // Load weekly calendar
  // -----------------------------
  useEffect(() => {
    if (tutorId) loadCalendar();
  }, [tutorId]);

  const loadCalendar = async (startOverride?: string) => {
    if (!tutorId) return;

    setLoading(true);

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
      setLoading(false);
    }
  };

  // -----------------------------
  // Shared booking response handler
  // -----------------------------
  const handleBookingResponse = (
    data: any,
    setMessage: (msg: string) => void
  ) => {
    const created = data.created || 0;
    const results = data.results || [];
    const failures = results.filter((r: any) => !r.success);

    if (created > 0) {
      if (failures.length === 0) {
        setMessage(`Booked ${created} session${created > 1 ? "s" : ""}.`);
      } else {
        const failList = failures
          .map((f: any) => `Week ${f.week}: ${f.reason}`)
          .join(", ");
        setMessage(
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
        setMessage(`No sessions booked. Reasons: ${failList}`);
      } else {
        setMessage("No sessions booked.");
      }
    }
  };

  // -----------------------------
  // WEEKLY SIDE
  // -----------------------------

  // Slot selection → show weekly modal
  const handleSelectWeeklySlot = (
    day: string,
    blockStart: string,
    blockEnd: string
  ) => {
    if (!tutorSettings) return;

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

    setWeeklySlotOptions({
      date: day,
      weekday: new Date(day).getDay(),
      blockStart,
      blockEnd,
      validStarts,
    });

    setShowWeeklyModal(true);
  };

  // Book weekly
  const handleBookWeekly = async (weekday: number, time: string) => {
    if (!student) return;

    setWeeklyBookingLoading(true);

    const payload = {
      student_id: student.id,
      weekday,
      time,
    };

    try {
      const res = await apiFetch(
        `/api/tutors/${student.tutor_id}/create_weekly_booking/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      const data = await res.json();

      if (data.error) {
        setWeeklyMessage(data.error);
      } else {
        setWeeklyMessage("Weekly session booked.");
      }

      // Reload weekly availability
      const availRes = await apiFetch(
        `/api/students/${student.id}/weekly_availability/`
      );
      setWeeklyAvailability(await availRes.json());
      const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
      setStudent(await homeRes.json());

    } finally {
      setWeeklyBookingLoading(false);
    }
  };


  // Delete weekly booking
  const handleDeleteWeeklyBooking = async (weekday: number, time: string) => {
    if (!tutorId) return;

    await apiFetch(`/api/tutors/${tutorId}/delete_weekly_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weekday, time }),
    });

    // Reload weekly availability
    const res = await apiFetch(`/api/students/${student.id}/weekly_availability/`);
    setWeeklyAvailability(await res.json());
  };

  // -----------------------------
  // AD HOC SIDE
  // -----------------------------

  const handleManualBooking = async () => {
    if (!manualDate || !manualTime || !student) {
      setAdHocMessage("Please choose a date and time.");
      return;
    }

    setAdHocBookingLoading(true);

    const payload = {
      student_id: student.id,
      date: manualDate,
      time: manualTime,
      repeat_weekly: false,
    };

    try {
      const res = await apiFetch(`/api/tutors/${tutorId}/check_and_book/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      handleBookingResponse(data, setAdHocMessage);
    } finally {
      setAdHocBookingLoading(false);
    }
  };

  const handleDeleteAdHocBooking = async (bookingId: number) => {
    if (!tutorId) return;

    await apiFetch(`/api/tutors/${tutorId}/delete_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: bookingId }),
    });

    setWeek(null);
    loadCalendar(weekStart || undefined);
  };

  // -----------------------------
  // Helpers to render “next” cards
  // -----------------------------
  const renderNextCard = (booking: any, title: string) => {
    if (!booking) {
      return (
        <div className="alert alert-secondary mt-3">
          You have no upcoming {title.toLowerCase()}.
        </div>
      );
    }

    const start = new Date(booking.start);

    const weekday = start.toLocaleDateString([], {
      weekday: "long",
    });

    const date = start.toLocaleDateString([], {
      day: "numeric",
      month: "long",
    });

    const time = start.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    return (
      <div className="alert alert-success mt-3">
        <strong>Your next {title.toLowerCase()}:</strong>
        <br />
        {weekday}, {date} at {time}
      </div>
    );
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
        <h1>Bookings for: {student.name}</h1>

        <div className="row mt-4">
          {/* LEFT: Weekly Appointments */}
          <div className="col-md-6">
            <h2>Weekly Appointments</h2>

            {renderNextCard(student.next_weekly_booking, "Weekly appointment")}

            {weeklyMessage && (
              <div className="alert alert-info mt-3">{weeklyMessage}</div>
            )}

            {weeklyBookingLoading && (
              <div className="text-center my-3">
                <div className="spinner-border text-success" role="status">
                  <span className="visually-hidden">Booking weekly…</span>
                </div>
                <div style={{ marginTop: "0.5rem", fontWeight: 500 }}>
                  Booking weekly session…
                </div>
              </div>
            )}

            <div className="mt-3 mb-2" style={{ fontWeight: 600 }}>
              {student?.tutor_name
                ? `${student.tutor_name}'s Available Appointments (click a time to make a weekly booking)`
                : "Tutor's Weekly Calendar"}
            </div>

            {loading && (
              <div className="text-center my-3">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Loading…</span>
                </div>
              </div>
            )}

            <div
              style={{
                opacity: loading ? 0.4 : 1,
                pointerEvents: loading ? "none" : "auto",
              }}
            >
            {weeklyAvailability && (
              <WeeklyBookingCalendar
                availability={weeklyAvailability}
                mode="student"
                onBook={handleBookWeekly}
                onDelete={handleDeleteWeeklyBooking}
              />
            )}

            </div>

            {/* Weekly booking modal */}
            {showWeeklyModal && weeklySlotOptions && tutorSettings && (
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
                <h3>Select a start time (weekly)</h3>

                {weeklySlotOptions.validStarts.length === 0 && (
                  <p>No valid start times available in this block.</p>
                )}

                {weeklySlotOptions.validStarts.map((t) => (
                  <button
                    key={t}
                    className="btn btn-primary m-1"
                    onClick={() => handleBookWeekly(weeklySlotOptions.weekday, t.slice(0, 5))}

                  >
                    {t}
                  </button>
                ))}

                <button
                  className="btn btn-secondary mt-3"
                  onClick={() => setShowWeeklyModal(false)}
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* RIGHT: Ad Hoc Appointments */}
          <div className="col-md-6">
            <h2>Ad Hoc Appointments</h2>

            {renderNextCard(student.next_ad_hoc_booking, "Ad hoc appointment")}

            {adHocMessage && (
              <div className="alert alert-info mt-3">{adHocMessage}</div>
            )}

            {adHocBookingLoading && (
              <div className="text-center my-3">
                <div className="spinner-border text-success" role="status">
                  <span className="visually-hidden">Booking session…</span>
                </div>
                <div style={{ marginTop: "0.5rem", fontWeight: 500 }}>
                  Booking ad hoc session…
                </div>
              </div>
            )}

            {/* Manual ad hoc booking */}
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

              <button
                className="btn btn-outline-primary"
                onClick={handleManualBooking}
                disabled={adHocBookingLoading}
              >
                {adHocBookingLoading ? "Booking…" : "Book Ad Hoc Session"}
              </button>
            </div>

            <div className="mt-4 mb-2" style={{ fontWeight: 600 }}>
              {student?.tutor_name
                ? `${student.tutor_name}'s Calendar`
                : "Tutor's Calendar"}
            </div>

            {loading && (
              <div className="text-center my-3">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Loading…</span>
                </div>
              </div>
            )}

            <div
              style={{
                opacity: loading ? 0.4 : 1,
                pointerEvents: loading ? "none" : "auto",
              }}
            >
              {week && (
                <WeeklyCalendar
                  week={week}
                  mode="student"
                  onSelectSlot={handleSelectWeeklySlot}
                  onDeleteBooking={handleDeleteAdHocBooking}
                />
              )}
            </div>
          </div>
        </div>

        {/* Week navigation (shared) */}
        <hr />
        <div className="d-flex align-items-center gap-3 mb-3">
          <button
            className="btn btn-outline-primary"
            onClick={() =>
              weekStart &&
              loadCalendar(
                getSundayStart(
                  new Date(
                    new Date(weekStart).setDate(
                      new Date(weekStart).getDate() - 7
                    )
                  )
                )
              )
            }
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
            onClick={() =>
              weekStart &&
              loadCalendar(
                getSundayStart(
                  new Date(
                    new Date(weekStart).setDate(
                      new Date(weekStart).getDate() + 7
                    )
                  )
                )
              )
            }
          >
            Next Week →
          </button>
        </div>
      </div>
    </Layout>
  );
}