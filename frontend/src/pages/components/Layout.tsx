import { Link } from "react-router-dom";
import { apiFetch, apiFetchJson } from "../../utils/apiFetch"




export function Layout({ children }: { children: React.ReactNode }) {

  const storedUser = localStorage.getItem("user");
  const user = storedUser ? JSON.parse(storedUser) : null;

  if (!localStorage.getItem("access")) {
    // User is not logged in
    return <div>{children}</div>;
  }

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (!stored) {
      window.location.href = "/login";
      return;
    }

    const user = JSON.parse(stored);

    if (user.role === "tutor") {
      window.location.href = `/tutor/${user.id}`;
    } else if (user.role === "student") {
      window.location.href = `/student/${user.id}`;
    } else if (user.role === "parent") {
      window.location.href = `/parent/${user.id}`;
    } else if (user.role === "admin") {
      window.location.href = `/admin`;
    }
  }, []);


  return (
    <>
      {/* Navbar */}
      <nav className="navbar navbar-expand-lg navbar-dark bg-dark mb-3">
        <div className="container-fluid">
          <Link className="navbar-brand" to="/templates">Tutor Platform</Link>
          <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNavbar"><span className="navbar-toggler-icon"></span></button>
          <div className="collapse navbar-collapse" id="mainNavbar">
            <ul className="navbar-nav me-auto mb-2 mb-lg-0">

              {user?.role === "admin" && (
                <>
                  <li className="nav-item"><Link className="nav-link" to="/admin/tutors">Tutors</Link></li>
                  <li className="nav-item"><Link className="nav-link" to="/admin/students">Students</Link></li>
                  <li className="nav-item"><Link className="nav-link" to="/templates">Templates</Link></li>
                  <li className="nav-item"><Link className="nav-link" to="/skills">Skills</Link></li>
                </>
              )}

              {user?.role === "tutor" && (
                <>
                  <li className="nav-item"><Link className="nav-link" to={`/tutor/${user.id}/`}>Home</Link></li>
                  <li className="nav-item"><Link className="nav-link" to="/templates">Templates</Link></li>
                  <li className="nav-item"><Link className="nav-link" to="/skills">Skills</Link></li>
                </>
              )}

              {user?.role === "student" && (
                <>
                  <li className="nav-item"><Link className="nav-link" to={`/student/${user.id}/`}>Home</Link></li>
                </>
              )}

              <li className="nav-item"><Link className="nav-link" to="/feedback">Feedback</Link></li>
              <li className="nav-item"><Link className="nav-link" to="/principles">Principles</Link></li>

              {!user && (
                <li className="nav-item"><Link className="nav-link" to="/login">Login</Link></li>
              )}

            </ul>
{user && (
  <>
<button
  className="btn btn-link text-white text-decoration-none"
  onClick={() => {
    apiFetch("/api/auth/logout/", {
      method: "POST",
      credentials: "include",
    });
    localStorage.removeItem("user");
    window.location.href = "/login";
  }}
>
  Logout
</button>


    <span className="navbar-text ms-3">
      Logged in as {user.first_name} ({user.role})
    </span>
  </>
)}



          </div>
        </div>
      </nav>

      {/* Page content */}
      <div className="container-fluid">{children}</div>
    </>
  );
}