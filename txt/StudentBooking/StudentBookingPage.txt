import { useParams } from "react-router-dom";
import React, { useState, useEffect } from "react";
import { Layout } from "./components/Layout";
import { apiFetch } from "../utils/apiFetch";
import { WeeklyBookingCalendar } from "./components/WeeklyBookingCalendar";

export function StudentBookingPage() {
  const { id } = useParams();
  const [student, setStudent] = useState<any>(null);

  const [weeklySlots, setWeeklySlots] = useState<any>(null);
  const [weeklyBookings, setWeeklyBookings] = useState<any>(null);

  const [adhocSlots, setAdhocSlots] = useState<any>(null);
  const [adhocBookings, setAdhocBookings] = useState<any>(null);

  const [modifyingWeekly, setModifyingWeekly] = useState(false);
  const [weeklyMessage, setWeeklyMessage] = useState("");
  const [weeklyBookingLoading, setWeeklyBookingLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiFetch(`/api/students/${id}/home/`)
      .then(res => res.json())
      .then(data => setStudent(data));
  }, [id]);

  useEffect(() => {
    if (!student) return;

    const load = async () => {
      const today = new Date();
      const sunday = new Date(today);
      sunday.setDate(today.getDate() - today.getDay());
      const weekStart = sunday.toISOString().slice(0, 10);

      const res = await apiFetch(
        `/api/students/${student.id}/booking/`
      );
      const data = await res.json();

      setWeeklySlots(data.weekly_slots);
      setWeeklyBookings(data.weekly_bookings);
      setAdhocSlots(data.adhoc_slots);
      setAdhocBookings(data.adhoc_bookings);
    };

    load();
  }, [student]);

  const handleBookWeekly = async (weekday: number, time: string) => {
    if (!student) return;
    setWeeklyBookingLoading(true);

    const payload = { student_id: student.id, weekday, time };

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
      setWeeklyMessage(data.error || `Weekly session booked (yet to be confirmed by your ${student.tutor_name}).`);

      const today = new Date();
      const sunday = new Date(today);
      sunday.setDate(today.getDate() - today.getDay());
      const weekStart = sunday.toISOString().slice(0, 10);

      const availRes = await apiFetch(
        `/api/students/${student.id}/booking/`
      );
      const avail = await availRes.json();

      setWeeklySlots(avail.weekly_slots);
      setWeeklyBookings(avail.weekly_bookings);
      setAdhocSlots(avail.adhoc_slots);
      setAdhocBookings(avail.adhoc_bookings);

      const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
      setStudent(await homeRes.json());
    } finally {
      setWeeklyBookingLoading(false);
    }
  };

  const handleDeleteWeeklyBooking = async (weekday: number, time: string) => {
    if (!student?.tutor_id) return;

    await apiFetch(`/api/tutors/${student.tutor_id}/delete_weekly_booking/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weekday, time }),
    });

    const today = new Date();
    const sunday = new Date(today);
    sunday.setDate(today.getDate() - today.getDay());
    const weekStart = sunday.toISOString().slice(0, 10);

    const res = await apiFetch(
      `/api/students/${student.id}/booking`
    );
    const data = await res.json();

    setWeeklySlots(data.weekly_slots);
    setWeeklyBookings(data.weekly_bookings);
    setAdhocSlots(data.adhoc_slots);
    setAdhocBookings(data.adhoc_bookings);
  };

  const handleDeleteAdhoc = async () => {
    if (!student?.id) return;

    await apiFetch(`/api/adhoc_bookings/delete_override/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: student.id }),
    });

    const res = await apiFetch(`/api/students/${student.id}/booking`);
    const data = await res.json();
    const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
    setStudent(await homeRes.json());

    setWeeklySlots(data.weekly_slots);
    setWeeklyBookings(data.weekly_bookings);
    setAdhocSlots(data.adhoc_slots);
    setAdhocBookings(data.adhoc_bookings);
  };



  const handlePauseWeekly = async (bookingId: number) => {
    if (!student) return;
    setWeeklyBookingLoading(true);

    try {
      await apiFetch(`/api/weekly_bookings/${bookingId}/skip/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const today = new Date();
      const sunday = new Date(today);
      sunday.setDate(today.getDate() - today.getDay());
      const weekStart = sunday.toISOString().slice(0, 10);

      const res = await apiFetch(
        `/api/students/${student.id}/booking/`
      );
      const data = await res.json();

      setWeeklySlots(data.weekly_slots);
      setWeeklyBookings(data.weekly_bookings);
      setAdhocSlots(data.adhoc_slots);
      setAdhocBookings(data.adhoc_bookings);

      const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
      setStudent(await homeRes.json());
    } finally {
      setWeeklyBookingLoading(false);
    }
  };

  const handleRemovePauseWeekly = async (bookingId: number) => {
    if (!student) return;
    setWeeklyBookingLoading(true);

    try {
      await apiFetch(`/api/weekly_bookings/${bookingId}/remove_skip/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const today = new Date();
      const sunday = new Date(today);
      sunday.setDate(today.getDate() - today.getDay());
      const weekStart = sunday.toISOString().slice(0, 10);

      const res = await apiFetch(
        `/api/students/${student.id}/booking/`
      );
      const data = await res.json();

      setWeeklySlots(data.weekly_slots);
      setWeeklyBookings(data.weekly_bookings);
      setAdhocSlots(data.adhoc_slots);
      setAdhocBookings(data.adhoc_bookings);

      const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
      setStudent(await homeRes.json());
    } finally {
      setWeeklyBookingLoading(false);
    }
  };

  const handleModifyWeekly = async (dateStr: string, time: string) => {
    if (!student) return;
    setWeeklyBookingLoading(true);

    try {
      const isoStart = new Date(`${dateStr}T${time}:00`).toISOString();

      // Single backend call
      await apiFetch(`/api/adhoc_bookings/modify_one_week/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: student.id,
          start: isoStart,
        }),
      });

      // Refresh booking + availability
      const availRes = await apiFetch(`/api/students/${student.id}/booking/`);
      const avail = await availRes.json();

      setWeeklySlots(avail.weekly_slots);
      setWeeklyBookings(avail.weekly_bookings);
      setAdhocSlots(avail.adhoc_slots);
      setAdhocBookings(avail.adhoc_bookings);

      const homeRes = await apiFetch(`/api/students/${student.id}/home/`);
      setStudent(await homeRes.json());

      setModifyingWeekly(false);
    } finally {
      setWeeklyBookingLoading(false);
    }
  };


  const renderNextCard = (booking: any) => {
    if (!booking) {
      return (
        <div className="alert alert-secondary mt-3">
          You have no upcoming appointments.
        </div>
      );
    }

    const start = new Date(booking.start);
    const weekday = start.toLocaleDateString([], { weekday: "long" });
    const date = start.toLocaleDateString([], { day: "numeric", month: "long" });
    const time = start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    return (
      <div className="alert alert-success mt-3">
        <strong>Your next appointment:</strong>
        <br />
        {weekday}, {date} at {time}
        {!booking.confirmed && (
          <span style={{ color: "#b00", fontWeight: 600 }}> (unconfirmed)</span>
        )}

        {student.booking_mode === "weekly_booking_but_adhoc_this_week" &&
          student.next_weekly_booking && (
            <div className="mt-2" style={{ fontSize: "0.9rem" }}>
              {(() => {
                const w = new Date(student.next_weekly_booking.start);
                const wDay = w.toLocaleDateString([], { weekday: "long" });
                const wTime = w.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                return (
                  <span className="text-muted">
                    Your regular weekly appointment is {wDay} at {wTime}. It will resume next week.
                  </span>
                );
              })()}
            </div>
          )}

        <div className="mt-3 d-flex gap-2">
          {student.booking_mode === "weekly_booking_but_adhoc_this_week" && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleDeleteAdhoc}
              disabled={weeklyBookingLoading || !booking.student_can_edit}
            >
              Delete this appointment
            </button>
          )}

          {student.booking_mode === "weekly_booking" && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setModifyingWeekly(true)}
              disabled={weeklyBookingLoading || !booking.student_can_edit}
            >
              Modify my time for this week
            </button>
          )}

          {(student.booking_mode === "weekly_booking" ) && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handlePauseWeekly(booking.id)}
              disabled={weeklyBookingLoading || !booking.student_can_edit}
            >
              Pause my appointment for one week
            </button>
          )}

          {(student.booking_mode === "weekly_booking_but_paused") && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleRemovePauseWeekly(booking.id)}
              disabled={weeklyBookingLoading || !booking.student_can_edit}
            >
              Remove one week pause
            </button>
          )}



        </div>
<div className="mt-3 text-muted" style={{ fontSize: "1rem" }}>
  If you have any questions about your appointment, call or text {student.tutor_name} on {student.tutor_mobile}.
</div>
      </div>
    );
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
        <h1>Bookings for: {student.name}</h1>

        <div className="row mt-4">
          <div className="col-md-12">
            <h2>Weekly Appointments</h2>

            {renderNextCard(student.next_booking)}

            {weeklyMessage && (
              <div className="alert alert-info mt-3">{weeklyMessage}</div>
            )}

            {weeklyBookingLoading && (
              <div className="text-center my-3">
                <div className="spinner-border text-success" role="status" />
                <div style={{ marginTop: "0.5rem", fontWeight: 500 }}>
                  Booking weekly session…
                </div>
              </div>
            )}

            {(!student.next_booking || modifyingWeekly) && (
              <div className="mt-3 mb-2" style={{ fontWeight: 600 }}>
                {student?.tutor_name
                  ? `${student.tutor_name}'s Available Appointments`
                  : "Tutor's Weekly Calendar"}
              </div>
            )}


            {modifyingWeekly && (
              <div className="alert alert-info mt-3">
                Select a new time for this week only.
              </div>
            )}

            <div
              style={{
                opacity: loading ? 0.4 : 1,
                pointerEvents: loading ? "none" : "auto",
              }}
            >
              {(student.booking_mode == "no_booking") && (
                <WeeklyBookingCalendar
                  availability={weeklySlots}
                  bookings={weeklyBookings}
                  mode="weekly"
                  onBook={handleBookWeekly}
                  onDelete={handleDeleteWeeklyBooking}
                />
              )}

              {modifyingWeekly && adhocSlots && (
                <WeeklyBookingCalendar
                  availability={adhocSlots}
                  bookings={adhocBookings}
                  mode="modify_weekly"
                  onBook={handleModifyWeekly}
                  onDelete={() => {}}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}