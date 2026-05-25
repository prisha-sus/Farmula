import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Bell,
  CloudSun,
  Compass,
  History,
  LineChart,
  Lock,
  LogOut,
  MapPin,
  Menu,
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
  X,
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
import { useTranslation } from "react-i18next";
import { API_BASE, apiRequest } from "./api";
import AlertsPanel from "./components/AlertsPanel";
import HarvestRecommendation from "./components/HarvestRecommendation";
import LanguageSwitcher from "./components/LanguageSwitcher";
import StyledSelect from "./components/StyledSelect";
import TraderCompare from "./components/TraderCompare";

const HORIZONS = [1, 7, 15, 30];
const DEFAULT_LOCATION = { farmer_lat: 18.65, farmer_lon: 73.8 };
const USER_KEY = "farmula:user";
const HISTORY_KEY = "farmula:history";
const DASHBOARD_PAGES = [
  "overview",
  "parameters",
  "recommendation",
  "history",
  "harvest",
  "trader",
  "alerts",
];

function getDashboardPageFromHash() {
  const hash = window.location.hash.replace("#", "");
  return DASHBOARD_PAGES.includes(hash) ? hash : "overview";
}

function setDashboardHash(page) {
  const nextPage = DASHBOARD_PAGES.includes(page) ? page : "overview";
  window.history.pushState({}, "", `${window.location.pathname}${window.location.search}#${nextPage}`);
}

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
  const { t } = useTranslation();
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
      setError(t("auth.passwordsDoNotMatch"));
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
        <h1>{t("app.name")} DSS</h1>
        <p>{t("auth.marketingTagline")}</p>
        <div className="auth-highlights">
          <span><ShieldCheck size={16} /> {t("auth.secureFarmerAccounts")}</span>
          <span><Route size={16} /> {t("auth.logisticsAwareNet")}</span>
          <span><Sparkles size={16} /> {t("auth.shapBackedAI")}</span>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">{t("auth.dashboardAccess")}</p>
            <h2>{mode === "login" ? t("auth.signInTitle") : t("auth.createAccountTitle")}</h2>
          </div>
          <LanguageSwitcher />
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "signup" && (
            <Field
              label={t("auth.fullName")}
              value={form.name}
              onChange={(value) => setForm((next) => ({ ...next, name: value }))}
              placeholder={t("auth.fullName")}
            />
          )}
          <Field
            label={t("auth.email")}
            type="email"
            value={form.email}
            onChange={(value) => setForm((next) => ({ ...next, email: value }))}
            placeholder="you@example.com"
          />
          <Field
            label={t("auth.password")}
            type="password"
            value={form.password}
            onChange={(value) => setForm((next) => ({ ...next, password: value }))}
            placeholder={mode === "signup" ? t("auth.passwordHint") : t("auth.password")}
          />
          {mode === "signup" && (
            <Field
              label={t("auth.confirmPassword")}
              type="password"
              value={form.confirm}
              onChange={(value) => setForm((next) => ({ ...next, confirm: value }))}
              placeholder={t("auth.confirmPassword")}
            />
          )}

          {error && <p className="error-text">{error}</p>}

          <button className="primary-button" type="submit" disabled={loading}>
            {mode === "login" ? <Lock size={18} /> : <UserPlus size={18} />}
            {mode === "login" ? t("auth.signIn") : t("auth.createAccount")}
          </button>
          {loading ? <div className="skeleton" /> : null}
        </form>

        <button
          className="google-button"
          type="button"
          onClick={() => {
            window.location.href = `${API_BASE}/auth/login`;
          }}
        >
          <img src="https://www.google.com/favicon.ico" alt="" />
          {t("auth.continueWithGoogle")}
        </button>

        <button
          className="text-button"
          type="button"
          onClick={() => {
            setError("");
            setMode(mode === "login" ? "signup" : "login");
          }}
        >
          {mode === "login" ? t("auth.createNewAccount") : t("auth.useExistingAccount")}
          <ArrowRight size={16} />
        </button>
      </section>
    </main>
  );
}

function Dashboard({ user, onLogout }) {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState(getDashboardPageFromHash);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Dynamic district-commodity state (loaded from API)
  const [districts, setDistricts] = useState([]);
  const [selectedDistrict, setSelectedDistrict] = useState("");
  const [commodities, setCommodities] = useState([]);
  const [commodity, setCommodity] = useState("");        // commodity_key: lowercase + underscores
  const [commodityHasForecast, setCommodityHasForecast] = useState(false);
  const [loadingDistricts, setLoadingDistricts] = useState(true);
  const [loadingCommodities, setLoadingCommodities] = useState(false);
  const [horizon, setHorizon] = useState(7);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [freshness, setFreshness] = useState(null);
  const [weather, setWeather] = useState(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [bestPrice, setBestPrice] = useState(null);
  const [bestPriceLoading, setBestPriceLoading] = useState(false);
  const [latestPrices, setLatestPrices] = useState([]);
  const [latestPricesLoading, setLatestPricesLoading] = useState(false);
  const [recommendation, setRecommendation] = useState(null);
  const [msp, setMsp] = useState(null);
  const [history, setHistory] = useState(getStoredHistory);
  const [activeTab, setActiveTab] = useState("analytics");
  const [loading, setLoading] = useState(false);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [error, setError] = useState("");

  // district is now driven by the dynamic selector
  const district = selectedDistrict;

  // Display name for the currently selected commodity
  const commodityDisplayName = useMemo(() => {
    const found = commodities.find((c) => c.commodity_key === commodity);
    return found ? found.commodity : commodity;
  }, [commodities, commodity]);

  useEffect(() => {
    const syncPage = () => setCurrentPage(getDashboardPageFromHash());
    window.addEventListener("hashchange", syncPage);
    return () => window.removeEventListener("hashchange", syncPage);
  }, []);

  // Load available districts on mount
  useEffect(() => {
    apiRequest("/market/districts")
      .then((data) => {
        setDistricts(data.districts);
        if (data.districts.length > 0) setSelectedDistrict(data.districts[0]);
      })
      .catch(() => setDistricts([]))
      .finally(() => setLoadingDistricts(false));
  }, []);

  // Load commodities whenever district changes
  useEffect(() => {
    if (!selectedDistrict) return;
    setLoadingCommodities(true);
    setCommodity("");
    setCommodities([]);
    setCommodityHasForecast(false);
    apiRequest(`/market/commodities?district=${encodeURIComponent(selectedDistrict)}`)
      .then((data) => {
        setCommodities(data.commodities);
        if (data.commodities.length > 0) {
          const first = data.commodities[0];
          setCommodity(first.commodity_key);
          setCommodityHasForecast(first.has_forecast);
        }
      })
      .catch(() => setCommodities([]))
      .finally(() => setLoadingCommodities(false));
  }, [selectedDistrict]);

  function openPage(page) {
    setCurrentPage(page);
    setDashboardHash(page);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    apiRequest("/market/freshness").then(setFreshness).catch(() => setFreshness(null));
  }, []);

  useEffect(() => {
    let active = true;
    setBestPriceLoading(true);
    setLatestPricesLoading(true);
    apiRequest(
      `/market/best-price?district=${encodeURIComponent(selectedDistrict)}&commodity=${encodeURIComponent(commodity)}`
    )
      .then((data) => active && setBestPrice(data))
      .catch(() => active && setBestPrice(null))
      .finally(() => active && setBestPriceLoading(false));

    apiRequest(
      `/market/latest-prices?district=${encodeURIComponent(selectedDistrict)}&commodity=${encodeURIComponent(commodity)}`
    )
      .then((data) => active && setLatestPrices(data.prices || []))
      .catch(() => active && setLatestPrices([]))
      .finally(() => active && setLatestPricesLoading(false));

    return () => {
      active = false;
    };
  }, [commodity, selectedDistrict]);

  useEffect(() => {
    let active = true;
    setWeatherLoading(true);
    apiRequest("/weather/current", {
      method: "POST",
      body: JSON.stringify(location),
    })
      .then((data) => active && setWeather(data.weather))
      .catch(() => active && setWeather(null))
      .finally(() => active && setWeatherLoading(false));

    return () => {
      active = false;
    };
  }, [location]);

  async function analyzeMarket() {
    if (!commodityHasForecast) {
      setError(
        `AI forecast not available for ${commodityDisplayName} in ${selectedDistrict}. ` +
        "Select a commodity with AI forecast for full analysis."
      );
      return;
    }

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
          commodity,   // already commodity_key (lowercase + underscores)
        }),
      });
      setRecommendation(data);

      const mspData = await apiRequest(
        `/msp/status?commodity=${encodeURIComponent(commodity)}&current_price=${encodeURIComponent(
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
      openPage("recommendation");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError(t("errors.gpsNotAvailable"));
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
        setError(t("errors.gpsFailed"));
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

  const navItems = [
    ["overview", t("nav.overview"), Target],
    ["parameters", t("nav.parameters"), Compass],
    ["recommendation", t("nav.recommendation"), LineChart],
    ["history", t("nav.history"), History],
    ["harvest", t("harvest.title"), Sparkles],
    ["trader", t("trader.title"), ShieldCheck],
    ["alerts", t("alerts.sectionTitle"), Bell],
  ];

  function renderPage() {
    if (currentPage === "overview") {
      return (
        <>
          <header className="hero-banner" id="overview">
            <div className="hero-content">
              <p className="eyebrow-light">AI-powered agricultural intelligence for Maharashtra</p>
              <h1>{t("dashboard.title")}</h1>
              <p className="hero-subtitle">
                Real-time mandi prices, AI forecasts, and farmer-first decision tools
              </p>
              {freshness?.has_data && (
                <div className="hero-stats">
                  <span>
                    <strong>{freshness.district_count}</strong> {t("hero.districts", "districts")}
                  </span>
                  <span>
                    <strong>{freshness.commodity_count}</strong> {t("hero.commodities", "commodities")}
                  </span>
                  <span>
                    <strong>20</strong> {t("hero.withAI", "with AI forecast")}
                  </span>
                </div>
              )}
            </div>
            <FreshnessBadge freshness={freshness} />
          </header>

          <section className="page-hero panel">
            <div>
              <p className="eyebrow">{t("nav.overview")}</p>
              <h2>{t("app.name")} DSS</h2>
              <p className="page-copy">
                Focus each decision in its own workspace: planning, recommendation, harvest timing,
                trader offer checks, and SMS alerts.
              </p>
            </div>
            <div className="page-actions">
              <button className="primary-button compact-button" onClick={() => openPage("parameters")}>
                <Compass size={18} />
                {t("parameters.title")}
              </button>
              <button className="ghost-button compact-button" onClick={() => openPage("alerts")}>
                <Bell size={18} />
                {t("alerts.sectionTitle")}
              </button>
            </div>
          </section>

          <section className="feature-grid">
            <FeatureCard
              icon={<Compass size={20} />}
              title={t("parameters.title")}
              body="Set crop, horizon, and farm location before running the main mandi analysis."
              action={t("nav.parameters")}
              onClick={() => openPage("parameters")}
            />
            <FeatureCard
              icon={<LineChart size={20} />}
              title={t("nav.recommendation")}
              body="View the best mandi result, price band, SHAP explanation, and MSP context in one place."
              action={t("nav.recommendation")}
              onClick={() => openPage("recommendation")}
            />
            <FeatureCard
              icon={<Sparkles size={20} />}
              title={t("harvest.title")}
              body="Check whether you should sell now or hold based on the forecast for your selected crop."
              action={t("harvest.checkRecommendation")}
              onClick={() => openPage("harvest")}
            />
            <FeatureCard
              icon={<ShieldCheck size={20} />}
              title={t("trader.title")}
              body="Compare a trader's quoted offer against current mandi averages and ranges."
              action={t("trader.checkOffer")}
              onClick={() => openPage("trader")}
            />
            <FeatureCard
              icon={<Bell size={20} />}
              title={t("alerts.sectionTitle")}
              body="Manage SMS alerts, test message delivery, and keep subscriptions in your chosen language."
              action={t("alerts.subscribe")}
              onClick={() => openPage("alerts")}
            />
            <FeatureCard
              icon={<History size={20} />}
              title={t("history.title")}
              body="Review recent recommendation runs stored in this browser."
              action={t("nav.history")}
              onClick={() => openPage("history")}
            />
          </section>

          <section className="grid xl:grid-cols-[0.9fr_1.1fr] gap-5">
            <BestPricePanel bestPrice={bestPrice} loading={bestPriceLoading} />
            <DecisionFlow />
          </section>
        </>
      );
    }

    if (currentPage === "parameters") {
      return (
        <>
          <PageHeader
            eyebrow={t("parameters.eyebrow")}
            title={t("parameters.title")}
            description="This page is only for setting the crop, horizon, and location before you run the core mandi recommendation."
            badge={<FreshnessBadge freshness={freshness} />}
          />

          <section className="grid xl:grid-cols-[1.08fr_0.92fr] gap-5">
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{t("parameters.eyebrow")}</p>
                  <h2>{t("parameters.title")}</h2>
                </div>
                <button className="ghost-button" onClick={() => setRecommendation(null)}>
                  <RefreshCw size={16} />
                  {t("parameters.clearResult")}
                </button>
              </div>

              <div className="control-grid">
                {/* District selector — dynamic */}
                <div className="field-block">
                  <span>{t("parameters.district")}</span>
                  {loadingDistricts ? (
                    <div className="skeleton" style={{ height: 44 }} />
                  ) : (
                    <StyledSelect
                      value={selectedDistrict}
                      onChange={setSelectedDistrict}
                      options={districts.map((d) => ({ value: d, label: d }))}
                      placeholder={t("parameters.selectDistrict", "Select district")}
                    />
                  )}
                </div>

                {/* Commodity selector — dynamic, driven by selected district */}
                <div className="field-block">
                  <span>{t("parameters.crop")}</span>
                  {loadingCommodities ? (
                    <div className="skeleton" style={{ height: 44 }} />
                  ) : (
                    <StyledSelect
                      value={commodity}
                      onChange={(value) => {
                        const selected = commodities.find((c) => c.commodity_key === value);
                        setCommodity(value);
                        setCommodityHasForecast(selected?.has_forecast ?? false);
                      }}
                      options={commodities.map((c) => ({
                        value: c.commodity_key,
                        label: c.commodity,
                        has_forecast: c.has_forecast,
                        records: c.records,
                      }))}
                      placeholder={t("parameters.selectCrop", "Select commodity")}
                      renderOption={(opt) => (
                        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span>{opt.label}</span>
                          <span
                            style={{
                              fontSize: "0.72rem",
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: opt.has_forecast
                                ? "var(--theme-primarySoft)"
                                : "var(--theme-bgSubtle)",
                              color: opt.has_forecast
                                ? "var(--theme-primary)"
                                : "var(--theme-textMuted)",
                              fontWeight: 600,
                            }}
                          >
                            {opt.has_forecast ? "AI forecast" : "Live price"}
                          </span>
                        </span>
                      )}
                    />
                  )}
                </div>

                <SelectControl
                  label={t("parameters.horizon")}
                  value={horizon}
                  onChange={(value) => setHorizon(Number(value))}
                  options={HORIZONS}
                  format={(value) => t("parameters.horizonDays", { count: Number(value) })}
                />
                <div className="field-block">
                  <span>{t("parameters.farmGps")}</span>
                  <button className="location-button" onClick={useCurrentLocation} disabled={gpsLoading}>
                    <Navigation size={18} />
                    {gpsLoading ? t("parameters.lockingLocation") : t("parameters.useCurrentLocation")}
                  </button>
                </div>
              </div>

              <div className="location-strip">
                <MapPin size={18} />
                <span>
                  {formatNumber(location.farmer_lat, 4)}, {formatNumber(location.farmer_lon, 4)}
                </span>
                <small>
                  {location === DEFAULT_LOCATION
                    ? t("parameters.defaultCoordinates")
                    : t("parameters.activeCoordinates")}
                </small>
              </div>

              <button className="primary-button analyze" onClick={analyzeMarket} disabled={loading}>
                <Route size={19} />
                {loading ? t("parameters.runningAnalysis") : t("parameters.findBestMandi")}
              </button>
              {loading ? <div className="skeleton" /> : null}
            </div>

            <div className="panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{t("farmOverview.eyebrow")}</p>
                  <h2>{t("farmOverview.title")}</h2>
                </div>
                <CloudSun size={22} className="muted-icon" />
              </div>
              <div className="overview-grid">
                <MapEmbed lat={location.farmer_lat} lon={location.farmer_lon} />
                <WeatherCard weather={weather} loading={weatherLoading} />
              </div>
            </div>
          </section>
        </>
      );
    }

    if (currentPage === "recommendation") {
      return (
        <>
          <PageHeader
            eyebrow={t("nav.recommendation")}
            title={t("nav.recommendation")}
            description="This page is dedicated to the main mandi recommendation result and its supporting analytics."
            badge={<FreshnessBadge freshness={freshness} />}
          />

          {!recommendation ? (
            <EmptyPageState
              title="No recommendation yet"
              body="Run the main analysis from the Parameters page and the result will appear here."
              actionLabel={t("nav.parameters")}
              onAction={() => openPage("parameters")}
            />
          ) : (
            <>
              <ResultHero recommendation={recommendation} />
              <MetricGrid recommendation={recommendation} />
              <MspBanner msp={msp} price={recommendation.gross_price_p50} />

              <div className="panel">
                <Tabs active={activeTab} onChange={setActiveTab} />
                {activeTab === "analytics" && (
                  <AnalyticsTab
                    commodity={commodityDisplayName}
                    recommendation={recommendation}
                    chartData={chartData}
                    interval={interval}
                    latestPrices={latestPrices}
                    latestPricesLoading={latestPricesLoading}
                  />
                )}
                {activeTab === "explanation" && (
                  <ExplanationTab explanation={recommendation.explanation} />
                )}
                {activeTab === "history" && <HistoryTab history={history} />}
              </div>
            </>
          )}
        </>
      );
    }

    if (currentPage === "history") {
      return (
        <>
          <PageHeader
            eyebrow={t("history.eyebrow")}
            title={t("history.title")}
            description="This page keeps only your recent recommendation runs so you can compare decisions without other dashboard noise."
          />
          <section className="panel compact-history">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">{t("history.eyebrow")}</p>
                <h2>{t("history.title")}</h2>
              </div>
            </div>
            <HistoryTable history={history} />
          </section>
        </>
      );
    }

    if (currentPage === "harvest") {
      return (
        <>
          <PageHeader
            eyebrow={t("harvest.title")}
            title={t("harvest.title")}
            description="Use this page only for harvest timing decisions: should you sell now or hold for a better expected price."
          />
          <HarvestRecommendation
            commodity={commodity}
            district={district}
            horizon={horizon}
            userEmail={user.email}
          />
        </>
      );
    }

    if (currentPage === "trader") {
      return (
        <>
          <PageHeader
            eyebrow={t("trader.title")}
            title={t("trader.title")}
            description="Use this page to sanity-check a local trader offer against recent mandi price data."
          />
          <TraderCompare commodity={commodity} district={district} />
        </>
      );
    }

    return (
      <>
        <PageHeader
          eyebrow={t("alerts.sectionTitle")}
          title={t("alerts.sectionTitle")}
          description="Use this page to test SMS delivery and manage active alert subscriptions in your selected language."
        />
        <AlertsPanel commodity={commodity} district={district} userEmail={user.email} />
      </>
    );
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <span><Wheat size={24} /></span>
          <div>
            <strong>{t("app.name")}</strong>
            <small>{t("app.tagline")}</small>
          </div>
        </div>

        <nav className="nav-stack">
          {navItems.map(([page, label, Icon]) => (
            <button
              key={page}
              type="button"
              className={currentPage === page ? "active" : ""}
              onClick={() => openPage(page)}
            >
              <Icon size={17} />
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-extras">
          <LanguageSwitcher />
        </div>

        <div className="user-card">
          {user.picture ? <img src={user.picture} alt="" /> : <div className="avatar">{user.name?.[0] || "U"}</div>}
          <div>
            <strong>{user.name || "User"}</strong>
            <small>{user.email}</small>
          </div>
          <button
            title={t("nav.signOut")}
            onClick={() => {
              localStorage.removeItem(USER_KEY);
              onLogout();
            }}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <button
        type="button"
        className={`sidebar-backdrop ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
        aria-label="Close menu"
      />

      <section className="workspace">
        <div className="mobile-toolbar">
          <button
            type="button"
            className="menu-toggle"
            onClick={() => setSidebarOpen((prev) => !prev)}
            aria-label="Open menu"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="mobile-brand">
            <Wheat size={16} />
            <span>{t("app.name")}</span>
          </div>
        </div>
        {error && <div className="alert error">{error}</div>}
        {renderPage()}
      </section>
    </main>
  );
}

function PageHeader({ eyebrow, title, description, badge = null }) {
  return (
    <header className="topbar page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className="page-copy">{description}</p> : null}
      </div>
      {badge}
    </header>
  );
}

function FeatureCard({ icon, title, body, action, onClick }) {
  return (
    <article className="feature-card">
      <div className="feature-card-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{body}</p>
      <button type="button" className="ghost-button compact-button" onClick={onClick}>
        {action}
      </button>
    </article>
  );
}

function EmptyPageState({ title, body, actionLabel, onAction }) {
  return (
    <section className="panel empty-page-state">
      <h2>{title}</h2>
      <p>{body}</p>
      <button type="button" className="primary-button compact-button" onClick={onAction}>
        {actionLabel}
      </button>
    </section>
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
      <StyledSelect
        value={value}
        onChange={onChange}
        options={options.map((option) => ({
          value: option,
          label: format(option),
        }))}
      />
    </label>
  );
}

function FreshnessBadge({ freshness }) {
  const { t } = useTranslation();
  if (!freshness) {
    return <span className="status-badge neutral">{t("dashboard.freshnessChecking")}</span>;
  }
  if (!freshness.has_data) {
    return <span className="status-badge warning">{t("dashboard.freshnessNoRecords")}</span>;
  }
  const coverage = freshness.district_count
    ? ` · ${freshness.district_count}d/${freshness.commodity_count}c`
    : "";
  if (freshness.days_ago === 0) {
    return <span className="status-badge good">{t("dashboard.freshnessUpdatedToday")}{coverage}</span>;
  }
  if (freshness.days_ago <= 3) {
    return (
      <span className="status-badge neutral">
        {t("dashboard.freshnessFromDate", { date: freshness.latest_date })}{coverage}
      </span>
    );
  }
  return (
    <span className="status-badge warning">
      {t("dashboard.freshnessStale", { date: freshness.latest_date })}
    </span>
  );
}

function WeatherCard({ weather, loading }) {
  const { t } = useTranslation();
  if (loading) {
    return <div className="skeleton" />;
  }
  return (
    <div className="weather-card">
      <div>
        <ThermometerSun size={21} />
        <span>{t("weather.title")}</span>
      </div>
      {weather ? (
        <>
          <strong>{weather.temperature} C</strong>
          <small>{t("weather.wind", { speed: weather.windspeed })}</small>
        </>
      ) : (
        <>
          <strong>{t("weather.unavailable")}</strong>
          <small>{t("weather.noLiveData")}</small>
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

function BestPricePanel({ bestPrice, loading }) {
  const { t } = useTranslation();
  if (loading) {
    return (
      <section className="panel">
        <div className="skeleton" />
      </section>
    );
  }
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("bestPrice.eyebrow")}</p>
          <h2>{t("bestPrice.title")}</h2>
        </div>
        <BarChart3 size={22} className="muted-icon" />
      </div>
      {bestPrice?.available ? (
        <div className="best-price">
          <strong>{bestPrice.best_market}</strong>
          <span>{formatMoney(bestPrice.best_price)}{t("result.perQtl")}</span>
          <p>
            {t("bestPrice.above", {
              amount: formatMoney(bestPrice.advantage),
              count: bestPrice.market_count,
            })}
          </p>
        </div>
      ) : (
        <p className="empty-text">{t("bestPrice.unavailable")}</p>
      )}
    </section>
  );
}

function DecisionFlow() {
  const { t } = useTranslation();
  const steps = [
    [t("decisionFlow.locate"), t("decisionFlow.locateDesc")],
    [t("decisionFlow.forecast"), t("decisionFlow.forecastDesc")],
    [t("decisionFlow.deduct"), t("decisionFlow.deductDesc")],
    [t("decisionFlow.optimize"), t("decisionFlow.optimizeDesc")],
  ];
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("decisionFlow.eyebrow")}</p>
          <h2>{t("decisionFlow.title")}</h2>
        </div>
      </div>
      <div className="flow-grid">
        {steps.map(([title, body], index) => (
          <div className="flow-step" key={index}>
            <span>{title}</span>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ResultHero({ recommendation }) {
  const { t } = useTranslation();
  return (
    <section className="result-hero">
      <div>
        <p className="eyebrow">{t("result.optimalDestination")}</p>
        <h2>{recommendation.recommended_mandi} {t("result.mandi")}</h2>
      </div>
      <div className="result-chip">
        <Target size={18} />
        {t("result.highestNetReturn")}
      </div>
    </section>
  );
}

function MetricGrid({ recommendation }) {
  const { t } = useTranslation();
  const metrics = [
    [t("result.highestNetPrice"), `${formatMoney(recommendation.net_price_p50)}${t("result.perQtl")}`, <Sparkles size={20} />],
    [t("result.grossMarketRate"), `${formatMoney(recommendation.gross_price_p50)}${t("result.perQtl")}`, <LineChart size={20} />],
    [t("result.transportCost"), `${formatMoney(recommendation.transport_cost)}${t("result.perQtl")}`, <Truck size={20} />],
    [t("result.distance"), `${formatNumber(recommendation.distance_km)} km`, <Route size={20} />],
  ];
  return (
    <section className="metric-grid">
      {metrics.map(([label, value, icon], index) => (
        <div className="metric-card" key={index}>
          <span>{icon}</span>
          <small>{label}</small>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}

function MspBanner({ msp, price }) {
  const { t } = useTranslation();
  if (!msp) return null;
  return (
    <div className={`alert ${msp.has_msp && msp.status === "below" ? "warning" : "good"}`}>
      <ShieldCheck size={18} />
      {msp.has_msp ? (
        <span>
          {t("msp.comparison", { price: formatMoney(price), msp: formatMoney(msp.msp) })}
          {msp.season ? ` ${t("msp.season", { season: msp.season })}` : ""}. {msp.message}
        </span>
      ) : (
        <span>{msp.message}</span>
      )}
    </div>
  );
}

function Tabs({ active, onChange }) {
  const { t } = useTranslation();
  const tabs = [
    ["analytics", t("tabs.analytics"), BarChart3],
    ["explanation", t("tabs.explanation"), Sparkles],
    ["history", t("tabs.history"), History],
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

function AnalyticsTab({ commodity, recommendation, chartData, interval, latestPrices, latestPricesLoading }) {
  const { t } = useTranslation();
  return (
    <div className="tab-content analytics-grid">
      <div>
        <h3>{t("analytics.priceRiskBounds")}</h3>
        <p>
          {t("analytics.priceBounds", {
            mandi: recommendation.recommended_mandi,
            low: formatMoney(interval.low),
            high: formatMoney(interval.high),
          })}
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
        <h3>{t("analytics.latestPrices", { commodity })}</h3>
        {latestPricesLoading ? <div className="skeleton" /> : <PriceTable prices={latestPrices} />}
      </div>
    </div>
  );
}

function ExplanationTab({ explanation }) {
  const { t } = useTranslation();
  return (
    <div className="tab-content explanation">
      <Sparkles size={22} />
      <p>{explanation}</p>
      <small>{t("explanation.subtitle")}</small>
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
  const { t } = useTranslation();
  if (!prices.length) {
    return <p className="empty-text">{t("analytics.noRows")}</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{t("analytics.market")}</th>
            <th>{t("analytics.modalPrice")}</th>
            <th>{t("analytics.date")}</th>
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
  const { t } = useTranslation();
  if (!history.length) {
    return <p className="empty-text">{t("history.empty")}</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{t("history.date")}</th>
            <th>{t("history.crop")}</th>
            <th>{t("history.horizon")}</th>
            <th>{t("history.targetMandi")}</th>
            <th>{t("history.netEstimate")}</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.date).toLocaleDateString("en-IN")}</td>
              <td>{row.crop}</td>
              <td>{t("history.horizonDaysCell", { count: row.horizon })}</td>
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
