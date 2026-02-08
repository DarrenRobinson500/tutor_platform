import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Layout } from "./components/Layout";
import { WeeklyAvailabilityEditor } from "./components/WeeklyAvailabilityEditor";
import { BlockedDaysEditor } from "./components/BlockedDaysEditor";
import { WeeklyCalendarSimple} from "./components/WeeklyCalendarSimple"
import { apiFetch } from "../utils/apiFetch"

export function TutorSchedulePage() {
  const { id } = useParams();
  const [availability, setAvailability] = useState<any[]>([]);
  const [blockedDays, setBlockedDays] = useState<any[]>([]);

  useEffect(() => {
    apiFetch(`/api/tutors/${id}/availability/`)
      .then(res => res.json())
      .then(data => {
        setAvailability(data.availability);
        setBlockedDays(data.blocked_days);
      });
  }, [id]);

  return (
    <Layout>
      <div className="container mt-4">
        <h2>My Schedule</h2>
        <p className="text-muted">Set your weekly availability and block out days.</p>


        <h4>Weekly Availability</h4>
        <WeeklyAvailabilityEditor
          tutorId={id!}
          availability={availability}
          setAvailability={setAvailability}
        />

        <hr className="mt-4" />

        <h4>Weekly Calendar</h4>
            <WeeklyCalendarSimple
              availability={availability}
              onRemove={(id) => {
                // call the same removeSlot logic you already use
                apiFetch(`/api/tutors/${id}/remove_availability/`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ id }),
                });

                setAvailability(availability.filter(a => a.id !== id));
              }}
            />

        <hr className="mt-4" />

        <h4>Blocked Days</h4>
        <BlockedDaysEditor
          tutorId={id!}
          blockedDays={blockedDays}
          setBlockedDays={setBlockedDays}
        />
      </div>
    </Layout>
  );
}