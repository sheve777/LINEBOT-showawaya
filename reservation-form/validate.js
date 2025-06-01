// validate.js

function isReservationValid() {
  const people = parseInt(document.getElementById("people").value);
  const seat = document.querySelector('input[name="seat"]:checked')?.value;

  if (seat === "カウンター席") {
    if (people < 1 || people > 3) {
      alert("カウンター席は1〜3名でご利用ください。");
      return false;
    }
  }

  if (seat === "テーブル席") {
    if (people < 3) {
      alert("テーブル席は3名以上からご利用いただけます。");
      return false;
    }
    if (people > 8) {
      alert("テーブル席は最大8名までご利用いただけます。");
      return false;
    }
  }

  return true; // OK
}
