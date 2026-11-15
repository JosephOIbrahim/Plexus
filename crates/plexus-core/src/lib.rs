//! Plexus core. This file only declares modules; the layers guard checks their ranks.

pub mod outcome;
mod predicate;
mod budget;

#[cfg(feature = "python")]
mod py;
