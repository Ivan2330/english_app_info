const zone = "Europe/Kyiv";
const localTime = new Intl.DateTimeFormat("en-CA", {
  timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const offsetFormat = new Intl.DateTimeFormat("en", { timeZone: zone, timeZoneName: "longOffset" });

export function kyivInput(value) {
  if (!value) return "";
  const fields = Object.fromEntries(localTime.formatToParts(new Date(value)).map(({ type, value: part }) => [type, part]));
  return `${fields.year}-${fields.month}-${fields.day}T${fields.hour}:${fields.minute}`;
}

export function fromKyiv(value) {
  if (!value) return null;
  const approximate = new Date(`${value}Z`);
  const offset = (date) => offsetFormat.formatToParts(date).find((part) => part.type === "timeZoneName").value.slice(3);
  const first = new Date(`${value}${offset(approximate)}`);
  return new Date(`${value}${offset(first)}`).toISOString();
}
