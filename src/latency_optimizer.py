class LatencyOptimizer:
    def __init__(self, dsl_hal):
        self.dsl_hal = dsl_hal

    def apply_profile(self, profile):
        if profile == 'fast':
            self.force_fast_path()
        elif profile == 'gaming':
            self.optimize_for_gaming()
        elif profile == 'stable':
            self.set_stable_profile()
        else:
            raise ValueError(f"Unknown latency profile: {profile}")

    def force_fast_path(self):
        self.dsl_hal.set_interleaving(enabled=False)
        self.dsl_hal.set_inp(value=0)

    def optimize_for_gaming(self):
        self.force_fast_path()
        # Additional optimizations for gaming can be added here
        # For example, prioritizing certain types of traffic
        print("Optimizing for gaming: Fast path enabled, INP reduced.")

    def set_stable_profile(self):
        self.dsl_hal.set_interleaving(enabled=True)
        # Set INP to a default stable value
        self.dsl_hal.set_inp(value=2)
        print("Setting stable profile: Interleaving enabled, INP at default.")