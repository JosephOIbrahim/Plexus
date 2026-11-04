//! A sliding-window budget for neuron wakes.

use std::collections::VecDeque;

/// A sliding-window budget for neuron wakes.
#[derive(Debug, Clone)]
pub struct Budget {
    /// The maximum number of wakes allowed per window.
    wakes: u32,
    /// The window size in seconds.
    window_s: f64,
    /// The timestamps of admitted wakes.
    timestamps: VecDeque<f64>,
    /// The number of consecutive trips.
    trips: u32,
    /// Whether the budget is muted.
    muted: bool,
}

impl Budget {
    /// Create a new budget with the given wake limit and window size.
    pub fn new(wakes: u32, window_s: f64) -> Self {
        Budget {
            wakes,
            window_s,
            timestamps: VecDeque::new(),
            trips: 0,
            muted: false,
        }
    }

    /// Peek at the budget status at the given time.
    pub fn peek(&self, now: f64) -> &'static str {
        if self.muted {
            return "mute";
        }
        let count = self.timestamps.iter().filter(|&&t| now < t + self.window_s).count() as u32;
        if count < self.wakes {
            "wake"
        } else {
            "trip"
        }
    }

    /// Admit a wake at the given time.
    pub fn admit(&mut self, now: f64) -> &'static str {
        if self.muted {
            return "mute";
        }
        // Remove old timestamps
        self.timestamps.retain(|&t| now < t + self.window_s);
        let count = self.timestamps.len() as u32;
        if count < self.wakes {
            // Add new timestamp
            self.timestamps.push_back(now);
            self.trips = 0;
            "wake"
        } else {
            // Trip
            self.trips += 1;
            if self.trips >= 3 {
                self.muted = true;
                "mute"
            } else {
                "trip"
            }
        }
    }
}
