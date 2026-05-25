import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { apiRequest } from "../api";

export default function TraderCompare({ commodity, district }) {
  const { t } = useTranslation();
  const [offer, setOffer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function compareOffer() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/trader/compare", {
        method: "POST",
        body: JSON.stringify({
          commodity: commodity.toLowerCase(),
          district: district.toLowerCase(),
          trader_offer: Number(offer),
        }),
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const verdictClass =
    result?.verdict === "trader_lower"
      ? "lower"
      : result?.verdict === "trader_higher"
      ? "higher"
      : "fair";
  const verdictText =
    result?.verdict === "trader_lower"
      ? t("trader.verdictLower")
      : result?.verdict === "trader_higher"
      ? t("trader.verdictHigher")
      : t("trader.verdictFair");

  return (
    <section id="trader" className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("trader.title")}</p>
          <h2>{t("trader.subtitle")}</h2>
        </div>
      </div>

      <label className="field">
        <span>{t("trader.offerLabel")}</span>
        <input
          type="number"
          value={offer}
          onChange={(event) => setOffer(event.target.value)}
          placeholder={t("trader.offerPlaceholder")}
          min="0"
        />
      </label>

      <button className="primary-button analyze" onClick={compareOffer} disabled={loading || !offer}>
        {loading ? t("parameters.runningAnalysis") : t("trader.checkOffer")}
      </button>
      {loading ? <div className="skeleton" /> : null}

      {error && <div className="alert error">{error}</div>}

      {result && (
        <div>
          <div className={`trader-verdict ${verdictClass}`}>{verdictText}</div>
          <p>
            {result.verdict === "trader_lower" &&
              t("trader.youCouldEarn", { amount: Math.abs(result.difference).toFixed(2) })}
            {result.verdict === "trader_higher" &&
              t("trader.traderHigherWarning", { amount: Math.abs(result.difference).toFixed(2) })}
            {result.verdict === "fair" && t("trader.fairOffer", { count: result.mandi_count })}
          </p>
          <div className="metric-grid">
            <div className="metric-card">
              <small>{t("trader.offerLabel")}</small>
              <strong>Rs. {Number(result.trader_offer).toLocaleString("en-IN")}</strong>
            </div>
            <div className="metric-card">
              <small>{t("trader.mandiAverage")}</small>
              <strong>Rs. {Number(result.mandi_average).toLocaleString("en-IN")}</strong>
            </div>
            <div className="metric-card">
              <small>{t("trader.mandiRange")}</small>
              <strong>
                Rs. {Number(result.mandi_min).toLocaleString("en-IN")} -{" "}
                {Number(result.mandi_max).toLocaleString("en-IN")}
              </strong>
            </div>
            <div className="metric-card">
              <small>{t("trader.difference")}</small>
              <strong>Rs. {Number(result.difference).toLocaleString("en-IN")}</strong>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
