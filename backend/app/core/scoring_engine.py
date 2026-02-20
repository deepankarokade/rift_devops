def calculate_score(total_time, commits):
    base = 100
    bonus = 10 if total_time < 300 else 0
    penalty = max(0, commits - 20) * 2
    return base + bonus - penalty
