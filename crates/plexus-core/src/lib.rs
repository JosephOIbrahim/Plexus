//! Plexus core. This file only declares modules; the layers guard checks their ranks.

mod predicate;
mod budget;

#[cfg(feature = "python")]
mod py;
