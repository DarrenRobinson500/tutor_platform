interface Availability {
  id: number;
  weekday: number;       // 0 = Sunday, 1 = Monday, ...
  start_time: string;    // "09:00"
  end_time: string;      // "17:00"
}

interface WeeklyCalendarProps {
  availability: Availability[];
  onRemove: (id: number) => void;
}

export function WeeklyCalendarSimple({ availability, onRemove }: WeeklyCalendarProps) {
  const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];

  // Group availability by weekday
  const grouped: Record<number, Availability[]> = {
    0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: []
  };

  availability.forEach(a => {
    grouped[a.weekday].push(a);
  });

  for (let day = 0; day < 7; day++) {
    grouped[day].sort((a, b) => a.start_time.localeCompare(b.start_time));
  }


  return (
    <div className="weekly-calendar mt-4">
      <div className="row text-center fw-bold mb-2">
        {days.map(day => (
          <div key={day} className="col border py-2 bg-light">
            {day}
          </div>
        ))}
      </div>

      <div className="row">
        {days.map((_, index) => (
          <div key={index} className="col border" style={{ minHeight: "120px" }}>
            {grouped[index].length === 0 && (
              <div className="text-muted small mt-2">No availability</div>
            )}

            {grouped[index].map(slot => (
            <div
              key={slot.id}
              className="p-1 m-1 bg-primary text-white rounded small d-flex justify-content-between align-items-center"
            >
              <span>{slot.start_time} – {slot.end_time}</span>

                <button
                  className="delete-btn"
                  onClick={() => onRemove(slot.id)}
                  aria-label="Delete availability"
                ></button>

            </div>

            ))}
          </div>
        ))}
      </div>
    </div>
  );
}