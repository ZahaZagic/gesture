class BoxingCareer:
    def __init__(self):
        self.cash = 500
        self.points = 0
        self.record = {"wins": 0, "losses": 0}
        self.stats = {"power": 10.0, "stamina": 10.0, "agility": 10.0}
        self.state_belt_won = False
        self.sponsor_tasks = [
            "Land 5 clean punches",
            "Win with more than half HP",
            "Score a 3-hit combo",
        ]
        self.completed_tasks = 0

    @classmethod
    def from_dict(cls, data):
        career = cls()
        if not data:
            return career
        career.cash = int(data.get("cash", career.cash))
        career.points = int(data.get("points", career.points))
        career.record = dict(data.get("record", career.record))
        career.stats = dict(data.get("stats", career.stats))
        career.state_belt_won = bool(data.get("state_belt_won", career.state_belt_won))
        career.completed_tasks = int(data.get("completed_tasks", career.completed_tasks))
        tasks = data.get("sponsor_tasks")
        if isinstance(tasks, list) and tasks:
            career.sponsor_tasks = tasks
        return career

    def to_dict(self):
        return {
            "cash": self.cash,
            "points": self.points,
            "record": self.record,
            "stats": self.stats,
            "state_belt_won": self.state_belt_won,
            "completed_tasks": self.completed_tasks,
            "sponsor_tasks": self.sponsor_tasks,
        }

    def current_world_rank(self):
        pressure_score = self.points + self.record["wins"] * 85 - self.record["losses"] * 40
        return max(1, 120 - pressure_score // 40)

    def is_unlocked(self, arena_id):
        if arena_id == "town":
            return True
        if arena_id == "city":
            return self.record["wins"] >= 5 and self.record["losses"] == 0
        if arena_id == "state":
            return self.points > 500
        if arena_id == "national":
            return self.state_belt_won
        if arena_id == "worldwide":
            return self.state_belt_won and self.current_world_rank() <= 10
        return False

    def can_enter(self, arena):
        return self.is_unlocked(arena["id"]) and self.cash >= arena["entry_fee"]

    def match_performance_score(self, landed_hits, combo_peak, hp_left_ratio):
        return 1.0 + landed_hits * 0.06 + combo_peak * 0.04 + hp_left_ratio * 0.25

    def match_reward(self, arena, performance_score):
        return int(arena["base_prize"] * performance_score)

    def apply_match_result(self, arena, won, landed_hits, combo_peak, hp_left_ratio):
        self.cash -= arena["entry_fee"]
        self.cash -= arena["upkeep"]
        if won:
            self.record["wins"] += 1
            score = self.match_performance_score(landed_hits, combo_peak, hp_left_ratio)
            payout = self.match_reward(arena, score)
            self.cash += payout
            self.points += int(arena["base_prize"] * 0.65 + landed_hits * 8 + combo_peak * 5)
            if arena["id"] == "state":
                self.state_belt_won = True
            if combo_peak >= 3:
                self.cash += 75
                self.completed_tasks += 1
            return payout
        self.record["losses"] += 1
        self.points += max(20, int(arena["base_prize"] * 0.12))
        return 0

    def train_cost(self, stat_name):
        base = {"power": 60, "stamina": 70, "agility": 65}[stat_name]
        return int(base + self.stats[stat_name] * 3.0)

    def apply_training(self, stat_name, quality_score):
        cost = self.train_cost(stat_name)
        if self.cash < cost:
            return False, 0.0, cost
        self.cash -= cost
        gain = max(0.25, min(2.4, quality_score))
        self.stats[stat_name] += gain
        return True, gain, cost
