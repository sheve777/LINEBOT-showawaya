document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("reservationForm");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!isReservationValid()) return;

    const formData = new FormData(form);

    const scriptURL = 'https://script.google.com/macros/s/AKfycbxR9tAhyFBMw0Ae8O8baabXuNYgpQ04Nbh-iXQz6p-ic3MzW__TvbFTeaoFZIEES31d/exec';

    try {
      const response = await fetch(scriptURL, {
        method: 'POST',
        body: formData, // ✅ FormData形式で送信（CORS通過のため）
      });

      const result = await response.text();

      alert("✅ ご予約ありがとうございます！\nGoogleカレンダーにも登録されました！\n\n応答: " + result);
      form.reset();

    } catch (err) {
      console.error("カレンダー送信エラー:", err);
      alert("⚠ ご予約は送信されましたが、Googleカレンダーへの登録に失敗しました。");
    }
  });
});
