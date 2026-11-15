//! The Outcome envelope (Blueprint v5.4 §4). Every Plexus call returns one: a status, a payload,
//! and a reason that is required whenever the status is not Ok. It is defined once, here; py.rs
//! shows it to Python as plexus._core.Outcome and builds every one through Outcome::new, so the
//! rules below are written in this file and nowhere else.
#![deny(clippy::unwrap_used, clippy::expect_used)]

/// Where a call stands.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    /// The call did what was asked. The payload, if there is one, is its result.
    Ok,
    /// Something the call needs is not there: a substrate, a model, a value it can hash.
    Unavailable,
    /// The call was refused: a gate denied it, or a limit was reached.
    Blocked,
}

impl Status {
    /// The status as Python spells it: "ok", "unavailable" or "blocked".
    pub fn name(self) -> &'static str {
        match self {
            Status::Ok => "ok",
            Status::Unavailable => "unavailable",
            Status::Blocked => "blocked",
        }
    }

    /// The status a name spells, exactly and in lowercase, or None for any other text.
    pub fn from_name(name: &str) -> Option<Status> {
        match name {
            "ok" => Some(Status::Ok),
            "unavailable" => Some(Status::Unavailable),
            "blocked" => Some(Status::Blocked),
            _ => None,
        }
    }
}

/// Why a call is not Ok.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reason {
    /// A snake_case code a caller can branch on, such as "non_finite".
    pub code: String,
    /// A sentence a person can read.
    pub detail: String,
    /// What is missing, in order: field names, paths, model ids. Unavailable alone names any.
    pub missing: Vec<String>,
}

/// A status, a payload for Ok alone, and a reason for every other status.
///
/// The fields are private, so an Outcome exists only through the constructors below, and each of
/// them keeps these rules:
/// - Ok carries no reason, and may carry a payload;
/// - Unavailable and Blocked carry no payload, and a reason whose code is snake_case and whose
///   detail is not blank;
/// - only Unavailable names what is missing.
#[derive(Debug, Clone, PartialEq)]
pub struct Outcome<T> {
    status: Status,
    payload: Option<T>,
    reason: Option<Reason>,
}

impl<T> Outcome<T> {
    /// Ok, carrying payload.
    pub fn ok(payload: T) -> Self {
        Outcome { status: Status::Ok, payload: Some(payload), reason: None }
    }

    /// Unavailable: something the call needs is not there. missing names it, in order.
    pub fn unavailable(code: &str, detail: &str, missing: Vec<String>) -> Result<Self, String> {
        let reason = Reason { code: code.to_string(), detail: detail.to_string(), missing };
        Self::new(Status::Unavailable, None, Some(reason))
    }

    /// Blocked: the call was refused.
    pub fn blocked(code: &str, detail: &str) -> Result<Self, String> {
        let reason = Reason { code: code.to_string(), detail: detail.to_string(), missing: Vec::new() };
        Self::new(Status::Blocked, None, Some(reason))
    }

    /// Any outcome, checked against the rules on the type. Err names the rule it breaks.
    pub fn new(status: Status, payload: Option<T>, reason: Option<Reason>) -> Result<Self, String> {
        let name = status.name();
        match (status, &reason) {
            (Status::Ok, None) => {}
            (Status::Ok, Some(_)) => {
                return Err("an ok outcome carries no reason: leave reason_code, reason and missing out".to_string());
            }
            (_, None) => {
                return Err(format!("a {name} outcome needs a reason: give a reason_code and a reason"));
            }
            (_, Some(r)) => {
                if payload.is_some() {
                    return Err(format!("a {name} outcome carries no payload; only an ok outcome does"));
                }
                if !is_snake_case(&r.code) {
                    return Err(format!(
                        "reason_code {:?} is not snake_case: a lowercase letter, then lowercase letters, digits and underscores",
                        r.code
                    ));
                }
                if r.detail.trim().is_empty() {
                    return Err(format!("a {name} outcome needs a reason that is not blank"));
                }
                if status != Status::Unavailable && !r.missing.is_empty() {
                    return Err(format!("a {name} outcome names nothing missing; only an unavailable outcome does"));
                }
            }
        }
        Ok(Outcome { status, payload, reason })
    }

    /// The status.
    pub fn status(&self) -> Status {
        self.status
    }

    /// True exactly when the status is Ok.
    pub fn is_ok(&self) -> bool {
        self.status == Status::Ok
    }

    /// The payload, which only an Ok outcome may carry.
    pub fn payload(&self) -> Option<&T> {
        self.payload.as_ref()
    }

    /// The reason, which every outcome but Ok carries.
    pub fn reason(&self) -> Option<&Reason> {
        self.reason.as_ref()
    }

    /// The same outcome with its payload passed through f. The status and the reason do not change.
    pub fn map<U>(self, f: impl FnOnce(T) -> U) -> Outcome<U> {
        Outcome { status: self.status, payload: self.payload.map(f), reason: self.reason }
    }
}

/// A lowercase ASCII letter, then lowercase ASCII letters, digits and underscores.
fn is_snake_case(code: &str) -> bool {
    let mut chars = code.chars();
    matches!(chars.next(), Some('a'..='z'))
        && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ok_carries_its_payload_and_no_reason() {
        let o = Outcome::ok(7);
        assert_eq!(o.status(), Status::Ok);
        assert!(o.is_ok());
        assert_eq!(o.payload(), Some(&7));
        assert_eq!(o.reason(), None);
    }

    #[test]
    fn unavailable_and_blocked_carry_a_reason_and_no_payload() -> Result<(), String> {
        let u: Outcome<i32> = Outcome::unavailable("non_finite", "temperature is NaN", vec!["temperature".to_string()])?;
        assert_eq!(u.status(), Status::Unavailable);
        assert!(!u.is_ok());
        assert_eq!(u.payload(), None);
        let r = u.reason().ok_or("an unavailable outcome lost its reason")?;
        assert_eq!((r.code.as_str(), r.detail.as_str()), ("non_finite", "temperature is NaN"));
        assert_eq!(r.missing, vec!["temperature".to_string()]);
        let b: Outcome<i32> = Outcome::blocked("gate_denied", "the gate refused the write")?;
        assert_eq!(b.status(), Status::Blocked);
        assert_eq!(b.reason().map(|r| r.missing.len()), Some(0));
        Ok(())
    }

    #[test]
    fn a_reason_is_required_whenever_the_status_is_not_ok() {
        assert!(Outcome::<i32>::new(Status::Unavailable, None, None).is_err());
        assert!(Outcome::<i32>::new(Status::Blocked, None, None).is_err());
        assert!(Outcome::<i32>::unavailable("", "a sentence", Vec::new()).is_err());
        assert!(Outcome::<i32>::blocked("gate_denied", " \t").is_err());
    }

    #[test]
    fn each_rule_is_checked() {
        let reason = |missing: Vec<String>| Some(Reason { code: "x".to_string(), detail: "y".to_string(), missing });
        assert!(Outcome::new(Status::Ok, Some(1), reason(Vec::new())).is_err());
        assert!(Outcome::new(Status::Unavailable, Some(1), reason(Vec::new())).is_err());
        assert!(Outcome::<i32>::new(Status::Blocked, None, reason(vec!["z".to_string()])).is_err());
        assert!(Outcome::<i32>::new(Status::Unavailable, None, reason(vec!["z".to_string()])).is_ok());
        assert!(Outcome::<i32>::new(Status::Ok, None, None).is_ok());
        for bad in ["NonFinite", "non-finite", "2fast", "_x", "non finite", "Non_finite"] {
            assert!(Outcome::<i32>::blocked(bad, "a sentence").is_err(), "{bad} passed as snake_case");
        }
        for good in ["non_finite", "unsupported_type", "limit2", "x"] {
            assert!(Outcome::<i32>::blocked(good, "a sentence").is_ok(), "{good} failed as snake_case");
        }
    }

    #[test]
    fn names_round_trip() {
        for s in [Status::Ok, Status::Unavailable, Status::Blocked] {
            assert_eq!(Status::from_name(s.name()), Some(s));
        }
        assert_eq!(Status::from_name("Ok"), None);
        assert_eq!(Status::from_name(""), None);
    }

    #[test]
    fn map_changes_the_payload_alone() -> Result<(), String> {
        assert_eq!(Outcome::ok(2).map(|x| x * 10).payload(), Some(&20));
        let b = Outcome::<i32>::blocked("limit_reached", "the window is full")?.map(|x| x.to_string());
        assert_eq!(b.status(), Status::Blocked);
        assert_eq!(b.reason().map(|r| r.code.as_str()), Some("limit_reached"));
        Ok(())
    }
}
