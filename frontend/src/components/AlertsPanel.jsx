import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { apiRequest } from "../api";

const ALERT_TYPES = [
  { value: "daily_price", key: "alerts.dailyPrice" },
  { value: "price_threshold", key: "alerts.priceThreshold" },
  { value: "harvest_recommendation", key: "alerts.harvestRecommendation" },
];

const ALERT_LABEL_KEY = {
  daily_price: "alerts.dailyPrice",
  price_threshold: "alerts.priceThreshold",
  harvest_recommendation: "alerts.harvestRecommendation",
};

export default function AlertsPanel({ commodity, district, userEmail }) {
  const { t, i18n } = useTranslation();
  const [phoneNumber, setPhoneNumber] = useState("");
  const [alertType, setAlertType] = useState("daily_price");
  const [thresholdPrice, setThresholdPrice] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  async function fetchAlerts() {
    if (!userEmail) return;
    try {
      const data = await apiRequest(`/alerts/list?user_email=${encodeURIComponent(userEmail)}`);
      setAlerts(data.alerts || []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    fetchAlerts();
  }, [userEmail]);

  async function sendTest() {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const language = (i18n.language || "en").split("-")[0];
      await apiRequest("/sms/test", {
        method: "POST",
        body: JSON.stringify({
          phone_number: phoneNumber,
          language,
          user_email: userEmail,
        }),
      });
      setStatus(t("alerts.testSent"));
    } catch (err) {
      setError(`${t("alerts.testFailed")}: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function subscribe() {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const language = (i18n.language || "en").split("-")[0];
      await apiRequest("/alerts/subscribe", {
        method: "POST",
        body: JSON.stringify({
          user_email: userEmail,
          phone_number: phoneNumber,
          commodity: commodity.toLowerCase(),
          district: district.toLowerCase(),
          language,
          alert_type: alertType,
          threshold_price: alertType === "price_threshold" ? Number(thresholdPrice) : null,
        }),
      });
      setStatus(t("alerts.subscribed"));
      setThresholdPrice("");
      await fetchAlerts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function removeAlert(alertId) {
    setLoading(true);
    setError("");
    try {
      await apiRequest(`/alerts/${alertId}`, { method: "DELETE" });
      await fetchAlerts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section id="alerts" className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("alerts.sectionTitle")}</p>
          <h2>{t("alerts.sectionDescription")}</h2>
        </div>
      </div>

      <label className="field">
        <span>{t("alerts.phoneNumber")}</span>
        <input
          type="tel"
          value={phoneNumber}
          placeholder={t("alerts.phonePlaceholder")}
          onChange={(event) => setPhoneNumber(event.target.value)}
        />
      </label>

      <button className="ghost-button" onClick={sendTest} disabled={loading || !phoneNumber}>
        {t("alerts.sendTest")}
      </button>
      {loading ? <div className="skeleton" /> : null}

      <label className="field-block" style={{ marginTop: "16px" }}>
        <span>{t("alerts.alertType")}</span>
        <select value={alertType} onChange={(event) => setAlertType(event.target.value)}>
          {ALERT_TYPES.map((item) => (
            <option key={item.value} value={item.value}>
              {t(item.key)}
            </option>
          ))}
        </select>
      </label>

      {alertType === "price_threshold" && (
        <label className="field" style={{ marginTop: "12px" }}>
          <span>{t("alerts.thresholdPrice")}</span>
          <input
            type="number"
            value={thresholdPrice}
            onChange={(event) => setThresholdPrice(event.target.value)}
            placeholder={t("alerts.thresholdHint")}
          />
        </label>
      )}

      <button
        className="primary-button analyze"
        onClick={subscribe}
        disabled={loading || !phoneNumber || (alertType === "price_threshold" && !thresholdPrice)}
      >
        {t("alerts.subscribe")}
      </button>

      {status && <div className="alert good">{status}</div>}
      {error && <div className="alert error">{error}</div>}

      <h3 style={{ marginTop: "16px" }}>{t("alerts.yourAlerts")}</h3>
      {!alerts.length && <p className="empty-text">{t("alerts.noAlerts")}</p>}
      {!!alerts.length && (
        <div className="alert-list">
          {alerts.map((alert) => (
            <div className="alert-item" key={alert.id}>
              <div>
                <strong>
                  {alert.commodity} • {alert.district}
                </strong>
                <p style={{ margin: "4px 0 0" }}>
                  {t(ALERT_LABEL_KEY[alert.alert_type] || "alerts.alertType")}
                  {alert.threshold_price ? ` • Rs. ${alert.threshold_price}` : ""}
                </p>
              </div>
              <button className="delete-btn" onClick={() => removeAlert(alert.id)} disabled={loading}>
                {t("alerts.delete")}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
