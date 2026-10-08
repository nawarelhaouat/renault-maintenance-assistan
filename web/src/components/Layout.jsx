import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, LogOut, MessageSquare, PanelLeft, SquarePen, Trash2, Wrench } from "lucide-react";
import { DASH_ROLES } from "../App";
import { api } from "../api";
import { useAuth } from "../auth";

const ROLES = { operator: "Opérateur", technician: "Technicien", manager: "Responsable", admin: "Administrateur" };

function groupByDate(conversations) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const week = today - 6 * 864e5;
  const buckets = { "Aujourd'hui": [], "7 derniers jours": [], "Plus ancien": [] };
  for (const c of conversations) {
    const t = new Date(c.updated_at).getTime();
    buckets[t >= today ? "Aujourd'hui" : t >= week ? "7 derniers jours" : "Plus ancien"].push(c);
  }
  return Object.entries(buckets).filter(([, items]) => items.length);
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebar") === "closed" || window.innerWidth < 768
  );
  const [conversations, setConversations] = useState([]);
  const [menu, setMenu] = useState(false);

  const refresh = useCallback(() => api.conversations().then(setConversations).catch(() => {}), []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggle = () =>
    setCollapsed((c) => {
      localStorage.setItem("sidebar", c ? "open" : "closed");
      return !c;
    });
  const closeOnMobile = () => window.innerWidth < 768 && setCollapsed(true);

  const remove = async (e, id) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Supprimer cette discussion ?")) return;
    await api.deleteConversation(id);
    await refresh();
    if (pathname === `/c/${id}`) navigate("/");
  };

  const name = user.full_name || user.username;
  const initials = name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const onAssistant = pathname === "/" || pathname.startsWith("/c/");

  return (
    <div className="app">
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-head">
          <div className="logo">
            <span className="logo-mark"><Wrench size={15} /></span>
            <span>Maintenance</span>
          </div>
          <button className="icon-btn" onClick={toggle} aria-label="Réduire le menu" title="Réduire le menu">
            <PanelLeft size={18} />
          </button>
        </div>

        <nav className="nav">
          <Link to="/" className={`nav-item ${onAssistant ? "active" : ""}`} onClick={closeOnMobile}>
            <MessageSquare size={17} />Assistant
          </Link>
          {DASH_ROLES.includes(user.role) && (
            <Link to="/dashboard" className={`nav-item ${pathname.startsWith("/dashboard") ? "active" : ""}`} onClick={closeOnMobile}>
              <LayoutDashboard size={17} />Dashboard
            </Link>
          )}
        </nav>

        <div className="section-head">
          <span>Discussions</span>
          <button className="icon-btn small" onClick={() => navigate("/", { state: { fresh: Date.now() } })}
                  aria-label="Nouvelle discussion" title="Nouvelle discussion">
            <SquarePen size={15} />
          </button>
        </div>
        <div className="convs">
          {groupByDate(conversations).map(([label, items]) => (
            <div key={label}>
              <div className="group-label">{label}</div>
              {items.map((c) => (
                <NavLink key={c.id} to={`/c/${c.id}`} onClick={closeOnMobile}
                         className={({ isActive }) => `conv ${isActive ? "active" : ""}`}>
                  <span>{c.title}</span>
                  <button className="del" onClick={(e) => remove(e, c.id)} aria-label="Supprimer" title="Supprimer">
                    <Trash2 size={14} />
                  </button>
                </NavLink>
              ))}
            </div>
          ))}
        </div>

        <div className="sidebar-foot">
          {menu && (
            <div className="popover foot-menu">
              <button onClick={logout}><LogOut size={16} />Se déconnecter</button>
            </div>
          )}
          <button className="user-btn" onClick={() => setMenu((o) => !o)}>
            <span className="avatar">{initials}</span>
            <span className="user-meta"><span>{name}</span><small>{ROLES[user.role]}</small></span>
          </button>
        </div>
      </aside>

      <main className="main">
        {collapsed && (
          <button className="icon-btn floating" onClick={toggle} aria-label="Ouvrir le menu" title="Ouvrir le menu">
            <PanelLeft size={18} />
          </button>
        )}
        <Outlet context={{ refresh }} />
      </main>
    </div>
  );
}