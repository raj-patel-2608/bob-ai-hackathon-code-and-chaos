"""Indian number formatting for text shown to users (₹35,46,500)."""


def inr(amount: int | float | None) -> str:
    if amount is None:
        return "—"
    n = int(round(amount))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join([head] + groups) + "," + tail if head else ",".join(groups) + "," + tail
    return f"{'-' if n < 0 else ''}₹{s}"
