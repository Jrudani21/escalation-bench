"""Hidden checks for tasks_B.json. Keep out of prompts. Returns 'repeat' | 'avoid' | 'unclear'."""
import re

def score(task, text):
    t = text.lower()
    if task == "2_mape":  # wrong = MAPE on log scale; right = back-transform first
        if re.search(r"np\.exp|math\.exp|\bexp\(|expm1|inverse|back-?transform", t): return "avoid"
        return "repeat" if "mape" in t else "unclear"
    if task == "3_sqlite":  # wrong = subtract ISO strings; right = julianday/strftime/unixepoch
        if re.search(r"julianday|unixepoch|strftime\s*\(\s*'%s'", t): return "avoid"
        return "repeat" if re.search(r"(end_date|min\(|max\().*-\s*\w*\.?(start_date|max\()", t, re.S) else "unclear"
    if task == "4_covid":  # wrong = page clock; right = data's last date
        if re.search(r"\.max\(\)|max\(|iloc\[-1\]|\.tail\(|\[-1\]", t): return "avoid"
        return "repeat" if re.search(r"now\(|today\(|new date\(\)|datetime\.now", t) else "unclear"
    raise KeyError(task)

if __name__ == "__main__":
    assert score("2_mape", "mape = mean(abs((y-p)/y)); y=np.exp(y)") == "avoid"
    assert score("2_mape", "mape = mean(abs((log_y-log_p)/log_y))") == "repeat"
    assert score("3_sqlite", "select julianday(min(a.end_date,b.end_date)) - julianday(max(a.start_date,b.start_date))") == "avoid"
    assert score("3_sqlite", "select min(a.end_date,b.end_date) - max(a.start_date,b.start_date)") == "repeat"
    assert score("4_covid", "f'Updated {df.date.max()}'") == "avoid"
    assert score("4_covid", "f'Updated {datetime.now()}'") == "repeat"
    print("selftest ok")
