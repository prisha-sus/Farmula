import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  CloudSun,
  Compass,
  History,
  LineChart,
  Loader2,
  Lock,
  LogOut,
  MapPin,
  Navigation,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
  ThermometerSun,
  Truck,
  UserPlus,
  Wheat,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { API_BASE, apiRequest } from "./api";

const COMMODITIES = ["Onion", "Potato", "Soyabean"];
const HORIZONS = [1, 7, 15, 30];
const COMMODITY_DISTRICT = {
  Onion: "nashik",
  Potato: "pune",
  Soyabean: "amravati",
};
const DEFAULT_LOCATION = { farmer_lat: 18.65, farmer_lon: 73.8 };
const USER_KEY = "farmula:user";
const HISTORY_KEY = "farmula:history";

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Rs. --";
  }
  return `Rs. ${Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: digits,
  });
}

function parseInterval(interval) {
  const matches = String(interval || "").match(/[\d,.]+/g) || [];
  const [low, high] = matches.map((item) => Number(item.replace(/,/g, "")));
  return {
    low: Number.isFinite(low) ? low : 0,
    high: Number.isFinite(high) ? high : 0,
  };
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

function getStoredHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function App() {
  const [user, setUser] = useState(getStoredUser);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("auth_token");
    if (!token) return;

    apiRequest(`/auth/verify?token=${encodeURIComponent(token)}`)
      .then((data) => {
        if (data.valid && data.user) {
          localStorage.setItem(USER_KEY, JSON.stringify(data.user));
          setUser(data.user);
        }
      })
      .finally(() => {
        params.delete("auth_token");
        const next = params.toString();
        window.history.replaceState(
          {},
          "",
          `${window.location.pathname}${next ? `?${next}` : ""}`
        );
      });
  }, []);

  if (!user) {
    return <AuthScreen onAuth={setUser} />;
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} />;
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");

    if (mode === "signup" && form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      const data = await apiRequest(
        mode === "login" ? "/auth/email/login" : "/auth/email/signup",
        {
          method: "POST",
          body: JSON.stringify(
            mode === "login"
              ? { email: form.email, password: form.password }
              : { name: form.name, email: form.email, password: form.password }
          ),
        }
      );
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      onAuth(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-visual">
        <div className="brand-mark">
          <Wheat size={28} />
        </div>
        <h1>Farmula DSS</h1>
        <p>Market intelligence, route-aware pricing, and explainable decisions for Indian crop selling.</p>
        <div className="auth-highlights">
          <span><ShieldCheck size={16} /> Secure farmer accounts</span>
          <span><Route size={16} /> Logistics-aware net price</span>
          <span><Sparkles size={16} /> SHAP-backed AI explanation</span>
        </div>
      </section>

      <section className="auth-panel">
        <div>
          <p className="eyebrow">Dashboard access</p>
          <h2>{mode === "login" ? "Sign in" : "Create account"}</h2>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "signup" && (
            <Field
              label="Full name"
              value={form.name}
              onChange={(value) => setForm((next) => ({ ...next, name: value }))}
              placeholder="Your name"
            />
          )}
          <Field
            label="Email"
            type="email"
            value={form.email}
            onChange={(value) => setForm((next) => ({ ...next, email: value }))}
            placeholder="you@example.com"
          />
          <Field
            label="Password"
            type="password"
            value={form.password}
            onChange={(value) => setForm((next) => ({ ...next, password: value }))}
            placeholder={mode === "signup" ? "Min. 8 characters" : "Password"}
          />
          {mode === "signup" && (
            <Field
              label="Confirm password"
              type="password"
              value={form.confirm}
              onChange={(value) => setForm((next) => ({ ...next, confirm: value }))}
              placeholder="Repeat password"
            />
          )}

          {error && <p className="error-text">{error}</p>}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <Loader2 className="spin" size={18} /> : mode === "login" ? <Lock size={18} /> : <UserPlus size={18} />}
            {mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <button
          className="google-button"
          type="button"
          onClick={() => {
            window.location.href = `${API_BASE}/auth/login`;
          }}
        >
          <img src="https://www.google.com/favicon.ico" alt="" />
          Continue with Google
        </button>

        <button
          className="text-button"
          type="button"
          onClick={() => {
            setError("");
            setMode(mode === "login" ? "signup" : "login");
          }}
        >
          {mode === "login" ? "Create a new account" : "Use an existing account"}
          <ArrowRight size={16} />
        </button>
      </section>
    </main>
  );
}

function Dashboard({ user, onLogout }) {
  const [commodity, setCommodity] = useState("Onion");
  const [horizon, setHorizon] = useState(7);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [freshness, setFreshness] = useState(null);
  const [weather, setWeather] = useState(null);
  const [bestPrice, setBestPrice] = useState(null);
  const [latestPrices, setLatestPrices] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [msp, setMsp] = useState(null);
  const [history, setHistory] = useState(getStoredHistory);
  const [activeTab, setActiveTab] = useState("analytics");
  const [loading, setLoading] = useState(false);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [error, setError] = useState("");

  const district = COMMODITY_DISTRICT[commodity];

  useEffect(() => {
    apiRequest("/market/freshness").then(setFreshness).catch(() => setFreshness(null));
  }, []);

  useEffect(() => {
    let active = true;
    apiRequest(
      `/market/best-price?district=${encodeURIComponent(district)}&commodity=${encodeURIComponent(
        commodity.toLowerCase()
      )}`
    )
      .then((data) => active && setBestPrice(data))
      .catch(() => active && setBestPrice(null));

    apiRequest(
      `/market/latest-prices?district=${encodeURIComponent(district)}&commodity=${encodeURIComponent(
        commodity.toLowerCase()
      )}`
    )
      .then((data) => active && setLatestPrices(data.prices || []))
      .catch(() => active && setLatestPrices([]));

    return () => {
      active = false;
    };
  }, [commodity, district]);

  useEffect(() => {
    let active = true;
    apiRequest("/weather/current", {
      method: "POST",
      body: JSON.stringify(location),
    })
      .then((data) => active && setWeather(data.weather))
      .catch(() => active && setWeather(null));

    return () => {
      active = false;
    };
  }, [location]);

  async function analyzeMarket() {
    setLoading(true);
    setError("");
    setRecommendation(null);
    setMsp(null);

    try {
      const data = await apiRequest("/get_recommendation", {
        method: "POST",
        body: JSON.stringify({
          ...location,
          horizon,
          commodity: commodity.toLowerCase(),
        }),
      });
      setRecommendation(data);

      const mspData = await apiRequest(
        `/msp/status?commodity=${encodeURIComponent(commodity.toLowerCase())}&current_price=${encodeURIComponent(
          data.gross_price_p50
        )}`
      );
      setMsp(mspData);

      const item = {
        id: crypto.randomUUID(),
        date: new Date().toISOString(),
        crop: commodity,
        horizon,
        mandi: data.recommended_mandi,
        net: data.net_price_p50,
      };
      const nextHistory = [item, ...history].slice(0, 8);
      setHistory(nextHistory);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
      setActiveTab("analytics");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError("GPS is not available in this browser");
      return;
    }
    setGpsLoading(true);
    setError("");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({
          farmer_lat: position.coords.latitude,
          farmer_lon: position.coords.longitude,
        });
        setGpsLoading(false);
      },
      () => {
        setError("Could not lock GPS. The dashboard is using default Pune coordinates.");
        setGpsLoading(false);
      },
      { enableHighAccuracy: true, timeout: 12000 }
    );
  }

  const interval = useMemo(
    () => parseInterval(recommendation?.confidence_interval),
    [recommendation]
  );
  const chartData = recommendation
    ? [
        {
          name: recommendation.recommended_mandi,
          floor: interval.low,
          range: Math.max(interval.high - interval.low, 0),
        },
      ]
    : [];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span><Wheat size={24} /></span>
          <div>
            <strong>Farmula</strong>
            <small>DSS Command Center</small>
          </div>
        </div>

        <nav className="nav-stack">
          <a className="active" href="#overview"><Target size={17} /> Overview</a>
          <a href="#parameters"><Compass size={17} /> Parameters</a>
          <a href="#recommendation"><LineChart size={17} /> Recommendation</a>
          <a href="#history"><History size={17} /> History</a>
        </nav>

        <div className="user-card">
          {user.picture ? <img src={user.picture} alt="" /> : <div className="avatar">{user.name?.[0] || "U"}</div>}
          <div>
            <strong>{user.name || "User"}</strong>
            <small>{user.email}</small>
          </div>
          <button
            title="Sign out"
            onClick={() => {
              localStorage.removeItem(USER_KEY);
              onLogout();
            }}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar" id="overview">
          <div>
            <p className="eyebrow">AI-powered geographic arbitrage</p>
            <h1>Farmula DSS Dashboard</h1>
          </div>
          <FreshnessBadge freshness={freshness} />
        </header>

        {error && <div className="alert error">{error}</div>}

        <section className="grid xl:grid-cols-[1.08fr_0.92fr] gap-5" id="parameters">
          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Market parameters</p>
                <h2>Plan the selling decision</h2>
              </div>
              <button className="ghost-button" onClick={() => setRecommendation(null)}>
                <RefreshCw size={16} />
                Clear Result
              </button>
            </div>

            <div className="control-grid">
              <SelectControl label="Crop" value={commodity} onChange={setCommodity} options={COMMODITIES} />
              <SelectControl
                label="Selling horizon"
                value={horizon}
                onChange={(value) => setHorizon(Number(value))}
                options={HORIZONS}
                format={(value) => `${value} day${Number(value) > 1 ? "s" : ""}`}
              />
              <div className="field-block">
                <span>Farm GPS</span>
                <button className="location-button" onClick={useCurrentLocation} disabled={gpsLoading}>
                  {gpsLoading ? <Loader2 className="spin" size={18} /> : <Navigation size={18} />}
                  {gpsLoading ? "Locking Location" : "Use Current Location"}
                </button>
              </div>
            </div>

            <div className="location-strip">
              <MapPin size={18} />
              <span>
                {formatNumber(location.farmer_lat, 4)}, {formatNumber(location.farmer_lon, 4)}
              </span>
              <small>{location === DEFAULT_LOCATION ? "Default Pune coordinates" : "Active farm coordinates"}</small>
            </div>

            <button className="primary-button analyze" onClick={analyzeMarket} disabled={loading}>
              {loading ? <Loader2 className="spin" size={19} /> : <Route size={19} />}
              {loading ? "Running Market Analysis" : "Find Best Mandi"}
            </button>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Live context</p>
                <h2>Farm overview</h2>
              </div>
              <CloudSun size={22} className="muted-icon" />
            </div>
            <div className="overview-grid">
              <MapEmbed lat={location.farmer_lat} lon={location.farmer_lon} />
              <WeatherCard weather={weather} />
            </div>
          </div>
        </section>

        {!recommendation && (
          <section className="grid xl:grid-cols-[0.9fr_1.1fr] gap-5">
            <BestPricePanel bestPrice={bestPrice} />
            <DecisionFlow />
          </section>
        )}

        {recommendation && (
          <section className="space-y-5" id="recommendation">
            <ResultHero recommendation={recommendation} />
            <MetricGrid recommendation={recommendation} />
            <MspBanner msp={msp} price={recommendation.gross_price_p50} />

            <div className="panel">
              <Tabs active={activeTab} onChange={setActiveTab} />
              {activeTab === "analytics" && (
                <AnalyticsTab
                  commodity={commodity}
                  recommendation={recommendation}
                  chartData={chartData}
                  interval={interval}
                  latestPrices={latestPrices}
                />
              )}
              {activeTab === "explanation" && (
                <ExplanationTab explanation={recommendation.explanation} />
              )}
              {activeTab === "history" && <HistoryTab history={history} />}
            </div>
          </section>
        )}

        <section id="history" className="panel compact-history">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Recent analysis</p>
              <h2>Local recommendation history</h2>
            </div>
          </div>
          <HistoryTable history={history} />
        </section>
      </section>
    </main>
  );
}

function Field({ label, value, onChange, type = "text", placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        required
      />
    </label>
  );
}

function SelectControl({ label, value, onChange, options, format = (item) => item }) {
  return (
    <label className="field-block">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {format(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function FreshnessBadge({ freshness }) {
  if (!freshness) {
    return <span className="status-badge neutral">Checking data</span>;
  }
  if (!freshness.has_data) {
    return <span className="status-badge warning">No price records</span>;
  }
  if (freshness.days_ago === 0) {
    return <span className="status-badge good">Prices updated today</span>;
  }
  if (freshness.days_ago <= 3) {
    return <span className="status-badge neutral">Prices from {freshness.latest_date}</span>;
  }
  return <span className="status-badge warning">Stale data: {freshness.latest_date}</span>;
}

function WeatherCard({ weather }) {
  return (
    <div className="weather-card">
      <div>
        <ThermometerSun size={21} />
        <span>Current Weather</span>
      </div>
      {weather ? (
        <>
          <strong>{weather.temperature} C</strong>
          <small>Wind {weather.windspeed} km/h</small>
        </>
      ) : (
        <>
          <strong>Unavailable</strong>
          <small>Open-Meteo did not return live weather</small>
        </>
      )}
    </div>
  );
}

function MapEmbed({ lat, lon }) {
  const delta = 0.08;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${lon - delta}%2C${lat - delta}%2C${lon + delta}%2C${lat + delta}&layer=mapnik&marker=${lat}%2C${lon}`;
  return <iframe className="map-frame" title="Farm location map" src={src} />;
}

function BestPricePanel({ bestPrice }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Before optimization</p>
          <h2>Best live mandi price</h2>
        </div>
        <BarChart3 size={22} className="muted-icon" />
      </div>
      {bestPrice?.available ? (
        <div className="best-price">
          <strong>{bestPrice.best_market}</strong>
          <span>{formatMoney(bestPrice.best_price)}/qtl</span>
          <p>
            {formatMoney(bestPrice.advantage)} above district average across {bestPrice.market_count} mandis.
          </p>
        </div>
      ) : (
        <p className="empty-text">Live price preview is unavailable for the selected crop.</p>
      )}
    </section>
  );
}

function DecisionFlow() {
  const steps = [
    ["Locate", "Farm GPS establishes the transport origin."],
    ["Forecast", "LightGBM quantile models project crop prices."],
    ["Deduct", "Logistics cost is subtracted per quintal."],
    ["Optimize", "The dashboard ranks the highest net return."],
  ];
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Decision flow</p>
          <h2>What runs behind each analysis</h2>
        </div>
      </div>
      <div className="flow-grid">
        {steps.map(([title, body]) => (
          <div className="flow-step" key={title}>
            <span>{title}</span>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ResultHero({ recommendation }) {
  return (
    <section className="result-hero">
      <div>
        <p className="eyebrow">Optimal destination</p>
        <h2>{recommendation.recommended_mandi} Mandi</h2>
      </div>
      <div className="result-chip">
        <Target size={18} />
        Highest net return
      </div>
    </section>
  );
}

function MetricGrid({ recommendation }) {
  const metrics = [
    ["Highest Net Price", `${formatMoney(recommendation.net_price_p50)}/qtl`, <Sparkles size={20} />],
    ["Gross Market Rate", `${formatMoney(recommendation.gross_price_p50)}/qtl`, <LineChart size={20} />],
    ["Transport Cost", `${formatMoney(recommendation.transport_cost)}/qtl`, <Truck size={20} />],
    ["Distance", `${formatNumber(recommendation.distance_km)} km`, <Route size={20} />],
  ];
  return (
    <section className="metric-grid">
      {metrics.map(([label, value, icon]) => (
        <div className="metric-card" key={label}>
          <span>{icon}</span>
          <small>{label}</small>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}

function MspBanner({ msp, price }) {
  if (!msp) return null;
  return (
    <div className={`alert ${msp.has_msp && msp.status === "below" ? "warning" : "good"}`}>
      <ShieldCheck size={18} />
      {msp.has_msp ? (
        <span>
          MSP comparison: current price {formatMoney(price)}/q, MSP {formatMoney(msp.msp)}/q
          {msp.season ? ` (${msp.season})` : ""}. {msp.message}
        </span>
      ) : (
        <span>{msp.message}</span>
      )}
    </div>
  );
}

function Tabs({ active, onChange }) {
  const tabs = [
    ["analytics", "Market Analytics", BarChart3],
    ["explanation", "AI Explanation", Sparkles],
    ["history", "Recommendation History", History],
  ];
  return (
    <div className="tabs">
      {tabs.map(([id, label, Icon]) => (
        <button key={id} className={active === id ? "active" : ""} onClick={() => onChange(id)}>
          <Icon size={16} />
          {label}
        </button>
      ))}
    </div>
  );
}

function AnalyticsTab({ commodity, recommendation, chartData, interval, latestPrices }) {
  return (
    <div className="tab-content analytics-grid">
      <div>
        <h3>Price risk bounds</h3>
        <p>
          Gross price at {recommendation.recommended_mandi} is likely between {formatMoney(interval.low)} and{" "}
          {formatMoney(interval.high)} per quintal.
        </p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 24, top: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
              <YAxis dataKey="name" type="category" width={110} />
              <Tooltip formatter={(value) => formatMoney(value)} />
              <Bar dataKey="floor" stackId="price" fill="transparent" />
              <Bar dataKey="range" stackId="price" fill="#0f766e" radius={[6, 6, 6, 6]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div>
        <h3>{commodity} latest mandi prices</h3>
        <PriceTable prices={latestPrices} />
      </div>
    </div>
  );
}

function ExplanationTab({ explanation }) {
  return (
    <div className="tab-content explanation">
      <Sparkles size={22} />
      <p>{explanation}</p>
      <small>Generated through SHAP analysis over the LightGBM tree model.</small>
    </div>
  );
}

function HistoryTab({ history }) {
  return (
    <div className="tab-content">
      <HistoryTable history={history} />
    </div>
  );
}

function PriceTable({ prices }) {
  if (!prices.length) {
    return <p className="empty-text">No latest mandi rows available.</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Modal price</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {prices.slice(0, 6).map((row) => (
            <tr key={`${row.market}-${row.date}`}>
              <td>{row.market}</td>
              <td>{formatMoney(row.modal_price)}</td>
              <td>{String(row.date).slice(0, 10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryTable({ history }) {
  if (!history.length) {
    return <p className="empty-text">No recommendations have been generated in this browser yet.</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Crop</th>
            <th>Horizon</th>
            <th>Target mandi</th>
            <th>Net estimate</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.date).toLocaleDateString("en-IN")}</td>
              <td>{row.crop}</td>
              <td>{row.horizon} days</td>
              <td>{row.mandi}</td>
              <td>{formatMoney(row.net)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
