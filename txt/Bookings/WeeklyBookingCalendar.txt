import React from "react";

interface WeeklySlot {
  slots: string[];
  bookings: Array<{
    start_time: string;
    end_time: string;
    student_name?: string;
    status?: string; // booked_self / booked_other
  }>;
}

interface WeeklyBookingCalendarProps {
  availability: Record<number, WeeklySlot>;
  mode: "tutor" | "student";
  onBook: (weekday: number, time: string) => void;
  onDelete: (weekday: number, time: string) => void;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function WeeklyBookingCalendar({
  availability,
  mode,
  onBook,
  onDelete,
}: WeeklyBookingCalendarProps) {

  function formatTime(time: string) {
    // time is "HH:MM" or "HH:MM:SS"
    const [h, m] = time.split(":");
    let hour = parseInt(h, 10);
    const minute = m;
    const ampm = hour >= 12 ? "pm" : "am";
    hour = hour % 12 || 12;
    return `${hour}:${minute}${ampm}`;
  }



  return (
    <div className="weekly-booking-grid" style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "0px" }}>
      {WEEKDAYS.map((day, weekday) => {
        const dayData = availability[weekday] || { slots: [], bookings: [] };

        return (
          <div key={weekday} className="day-column" style={{ border: "1px solid #ccc", padding: "10px", borderRadius: "6px" }}>
            <h5 style={{ textAlign: "center" }}>{day}</h5>


            {/* Available slots */}
            {dayData.slots.length === 0 && (
              <div className="text-muted" style={{ fontSize: "0.85rem" }}>
                No available slots
              </div>
            )}

            {dayData.slots.map((time) => (
              <button
                key={time}
                className="btn btn-outline-primary w-100 mb-2"
                style={{ fontSize: "0.8rem", padding: "4px 6px" }}

                onClick={() => onBook(weekday, time)}
              >
                {formatTime(time)}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}