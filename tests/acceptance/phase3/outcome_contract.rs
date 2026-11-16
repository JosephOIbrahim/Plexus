//! M2b · The Outcome envelope, read from Rust (Blueprint v5.4 §4).
//!
//! test_outcome.py cannot see where the rules live: a Python class that checks them itself would
//! pass it. This file builds Outcomes through plexus_core::outcome alone, so every rule must be in
//! the Rust type. CONTRACT.md pins the surface it calls. Cargo runs it through the [[test]] entry in
//! crates/plexus-core/Cargo.toml, so the `cargo` gate and Plexus CI's cargo step read it.

use plexus_core::outcome::{Outcome, Reason, Status};

fn reason(code: &str, detail: &str, missing: &[&str]) -> Option<Reason> {
    Some(Reason {
        code: code.to_string(),
        detail: detail.to_string(),
        missing: missing.iter().map(|m| m.to_string()).collect(),
    })
}

#[test]
fn ok_carries_its_payload_and_no_reason() {
    let o = Outcome::ok(7);
    assert_eq!(o.status(), Status::Ok);
    assert!(o.is_ok());
    assert_eq!(o.payload(), Some(&7));
    assert!(o.reason().is_none());

    let bare = Outcome::<i32>::new(Status::Ok, None, None).expect("an ok outcome with no payload is valid");
    assert!(bare.is_ok());
    assert_eq!(bare.payload(), None);
}

#[test]
fn unavailable_and_blocked_are_built_with_a_reason_and_no_payload() {
    let u = Outcome::<i32>::unavailable("non_finite", "temperature is NaN", vec!["temperature".to_string(), "exposure".to_string()])
        .expect("a valid unavailable outcome was refused");
    assert_eq!(u.status(), Status::Unavailable);
    assert!(!u.is_ok());
    assert_eq!(u.payload(), None);
    let r = u.reason().expect("an unavailable outcome carries its reason");
    assert_eq!((r.code.as_str(), r.detail.as_str()), ("non_finite", "temperature is NaN"));
    assert_eq!(r.missing, vec!["temperature".to_string(), "exposure".to_string()], "missing keeps its order");

    let b = Outcome::<i32>::blocked("gate_denied", "the publication gate refused the write").expect("a valid blocked outcome was refused");
    assert_eq!(b.status(), Status::Blocked);
    assert!(!b.is_ok());
    assert_eq!(b.payload(), None);
    let r = b.reason().expect("a blocked outcome carries its reason");
    assert_eq!((r.code.as_str(), r.detail.as_str()), ("gate_denied", "the publication gate refused the write"));
    assert!(r.missing.is_empty());
}

#[test]
fn a_status_that_is_not_ok_needs_a_reason() {
    for status in [Status::Unavailable, Status::Blocked] {
        assert!(Outcome::<i32>::new(status, None, None).is_err(), "{status:?} with no reason was built");
    }
}

#[test]
fn ok_carries_no_reason_and_only_ok_carries_a_payload() {
    assert!(Outcome::new(Status::Ok, Some(1), reason("gate_denied", "a sentence", &[])).is_err());
    assert!(Outcome::<i32>::new(Status::Ok, None, reason("gate_denied", "a sentence", &[])).is_err());
    assert!(Outcome::new(Status::Unavailable, Some(1), reason("non_finite", "a sentence", &[])).is_err());
    assert!(Outcome::new(Status::Blocked, Some(1), reason("gate_denied", "a sentence", &[])).is_err());
}

#[test]
fn only_unavailable_names_what_is_missing() {
    assert!(Outcome::<i32>::new(Status::Blocked, None, reason("gate_denied", "a sentence", &["temperature"])).is_err());
    assert!(Outcome::<i32>::new(Status::Unavailable, None, reason("non_finite", "a sentence", &["temperature"])).is_ok());
}

#[test]
fn a_reason_code_is_snake_case_on_either_status() {
    for bad in ["", "NonFinite", "nonFinite", "non_Finite", "non-finite", "non finite", "2fast", "_hidden", "limit\u{b2}", "non_finite\n"] {
        assert!(Outcome::<i32>::blocked(bad, "a sentence").is_err(), "blocked took the code {bad:?}");
        assert!(Outcome::<i32>::unavailable(bad, "a sentence", Vec::new()).is_err(), "unavailable took the code {bad:?}");
    }
    for good in ["non_finite", "unsupported_type", "limit2", "x", "a__b", "non_"] {
        assert!(Outcome::<i32>::blocked(good, "a sentence").is_ok(), "blocked refused the code {good:?}");
        assert!(Outcome::<i32>::unavailable(good, "a sentence", Vec::new()).is_ok(), "unavailable refused the code {good:?}");
    }
}

#[test]
fn a_blank_reason_is_no_reason_on_either_status() {
    for blank in ["", " ", " \t", "\n", "\r\n", "\u{a0}", "\u{3000}", "\u{b}", "\u{2028}"] {
        assert!(Outcome::<i32>::blocked("gate_denied", blank).is_err(), "blocked took the reason {blank:?}");
        assert!(Outcome::<i32>::unavailable("non_finite", blank, Vec::new()).is_err(), "unavailable took the reason {blank:?}");
    }
    assert!(Outcome::<i32>::blocked("gate_denied", "line one\nline two").is_ok());
}

#[test]
fn status_names_are_exact() {
    for s in [Status::Ok, Status::Unavailable, Status::Blocked] {
        assert_eq!(Status::from_name(s.name()), Some(s));
    }
    assert_eq!((Status::Ok.name(), Status::Unavailable.name(), Status::Blocked.name()), ("ok", "unavailable", "blocked"));
    for not_a_name in ["OK", "Ok", " ok", "ok\n", "Blocked", "", "failed"] {
        assert_eq!(Status::from_name(not_a_name), None, "{not_a_name:?} read as a status");
    }
}

#[test]
fn map_changes_the_payload_alone() {
    let o = Outcome::ok(2).map(|x| x * 10);
    assert_eq!((o.status(), o.payload()), (Status::Ok, Some(&20)));
    let b = Outcome::<i32>::blocked("limit_reached", "the window is full").expect("valid").map(|x| x.to_string());
    assert_eq!(b.status(), Status::Blocked);
    assert_eq!(b.payload(), None);
    assert_eq!(b.reason().map(|r| r.code.as_str()), Some("limit_reached"));
}
