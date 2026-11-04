/** The business number with "108" in red: 905 905 1085 is easy to remember that way. */
export function PhoneText({ value }: { value: string }) {
  const at = value.indexOf("108");
  if (at < 0) return <>{value}</>;
  return (
    <>
      {value.slice(0, at)}
      <span className="ph-108">108</span>
      {value.slice(at + 3)}
    </>
  );
}
