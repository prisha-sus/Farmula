import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { apiRequest } from "../api";

function verdictMeta(t, recommendation, change, horizon) {
  if (recommendation === "sell_now") {
    return {
      className: "sell-now",
      title: t("harvest.sellNow"),
      reason: t("harvest.sellNowReason", { change, horizon }),
    };
  }
  if (recommendation === "hold") {
    return {
      className: "hold",
      title: t("harvest.hold"),
      reason: t("harvest.holdReason", { change, horizon }),
    };
  }
  return {
    className: "neutral",
    title: t("harvest.neutral"),
    reason: t("harvest.neutralReason"),
  };
}

export default function HarvestRecommendation({ commodity, district, horizon, userEmail }) {
  const { t, i18n } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [sendSms, setSendSms] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState("");

  async function fetchRecommendation() {
    setLoading(true);
    setError("");
    try {
      const language = (i18n.language || "en").split("-")[0];
      const payload = {
        commodity: commodity.toLowerCase(),
        district: district.toLowerCase(),
        horizon,
        language,
        user_email: userEmail,
        phone_number: sendSms ? phoneNumber : null,
      };

      const data = await apiRequest("/harvest/recommendation", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const meta = result
    ? verdictMeta(t, result.recommendation, Math.abs(result.change_pct), result.horizon)
    : null;

  return (
    <section id="harvest" className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("harvest.title")}</p>
          <h2>{t("harvest.subtitle")}</h2>
        </div>
      </div>

      <label className="field-block">
        <span>
          <input
            type="checkbox"
            checked={sendSms}
            onChange={(event) => setSendSms(event.target.checked)}
          />{" "}
          {t("harvest.alsoSendSms")}
        </span>
      </label>

      {sendSms && (
        <label className="field phone-input">
          <span>{t("alerts.phoneNumber")}</span>
          <input
            type="tel"
            value={phoneNumber}
            onChange={(event) => setPhoneNumber(event.target.value)}
            placeholder={t("alerts.phonePlaceholder")}
          />
        </label>
      )}

      <button className="primary-button analyze" onClick={fetchRecommendation} disabled={loading}>
        {loading ? t("parameters.runningAnalysis") : t("harvest.checkRecommendation")}
      </button>
      {loading ? <div className="skeleton" /> : null}

      {error && <div className="alert error">{error}</div>}

      {result && meta && (
        <div>
          <div className={`harvest-verdict ${meta.className}`}>{meta.title}</div>
          <p>{meta.reason}</p>
          <div className="metric-grid">
            <div className="metric-card">
              <small>{t("harvest.todayPrice")}</small>
              <strong>Rs. {Number(result.today_price).toLocaleString("en-IN")}/qtl</strong>
            </div>
            <div className="metric-card">
              <small>{t("harvest.futurePrice", { horizon: result.horizon })}</small>
              <strong>Rs. {Number(result.future_price_p50).toLocaleString("en-IN")}/qtl</strong>
            </div>
            <div className="metric-card">
              <small>{t("harvest.change")}</small>
              <strong>{Number(result.change_pct).toFixed(2)}%</strong>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
