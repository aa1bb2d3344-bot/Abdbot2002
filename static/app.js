const intervalEl = document.getElementById("interval");
const signalEl = document.getElementById("signal");
const priceEl = document.getElementById("price");
const updatedEl = document.getElementById("updated");

const fields = {
  entry: document.getElementById("entry"),
  sl: document.getElementById("sl"),
  tp1: document.getElementById("tp1"),
  tp2: document.getElementById("tp2"),
  tp3: document.getElementById("tp3"),
  tp4: document.getElementById("tp4"),
  rsi: document.getElementById("rsi"),
  e20: document.getElementById("e20"),
  e50: document.getElementById("e50"),
  e200: document.getElementById("e200")
};

function fmt(value, digits = 2) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function updateSignalClass(signal) {
  signalEl.classList.remove("buy", "sell", "wait");

  if (signal === "BUY") {
    signalEl.classList.add("buy");
  } else if (signal === "SELL") {
    signalEl.classList.add("sell");
  } else {
    signalEl.classList.add("wait");
  }
}

async function loadAnalysis() {
  const interval = intervalEl.value;

  try {
    signalEl.textContent = "جاري التحليل...";

    const response = await fetch(
      `/api/analysis?interval=${encodeURIComponent(interval)}`,
      { cache: "no-store" }
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(
        data.error || "حدث خطأ أثناء جلب البيانات"
      );
    }

    signalEl.textContent = data.signal || "WAIT";
    updateSignalClass(data.signal);

    priceEl.textContent = fmt(data.price);

    fields.entry.textContent = fmt(data.entry);
    fields.sl.textContent = fmt(data.sl);
    fields.tp1.textContent = fmt(data.tp1);
    fields.tp2.textContent = fmt(data.tp2);
    fields.tp3.textContent = fmt(data.tp3);
    fields.tp4.textContent = fmt(data.tp4);

    fields.rsi.textContent = fmt(data.rsi14);
    fields.e20.textContent = fmt(data.ema20);
    fields.e50.textContent = fmt(data.ema50);
    fields.e200.textContent = fmt(data.ema200);

    if (data.updated) {
      const date = new Date(data.updated);

      updatedEl.textContent =
        "آخر تحديث: " +
        date.toLocaleTimeString("ar-IQ", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        });
    }

  } catch (error) {
    console.error(error);

    signalEl.textContent = "خطأ";
    signalEl.classList.remove("buy", "sell");
    signalEl.classList.add("wait");

    updatedEl.textContent = error.message;
  }
}

intervalEl.addEventListener("change", loadAnalysis);

loadAnalysis();

// تحديث البيانات تلقائيًا كل 15 ثانية
setInterval(loadAnalysis, 15000);
