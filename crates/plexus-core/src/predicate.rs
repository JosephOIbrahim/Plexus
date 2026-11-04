//! Predicate grammar v0 (PLEXUS_SPEC.md §4), in plain Rust.
//!
//! predicate := clause { "AND" clause }
//! clause    := "changed(" path ")" | "delta(" path ")" cmp number
//!            | "attr(" path ")" cmp literal | "exists(" path ")"
//! cmp       := ">" | ">=" | "<" | "<=" | "==" | "!="
//!
//! No OR. Every path is absolute and inside the neuron's scope. This file names nothing
//! outside std: no other module of this crate and no Python types; py.rs wraps it.

use std::collections::HashMap;

/// A composed attribute value as Python hands it over. It holds a `String`, so it is
/// never `Copy`.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Num(f64),
    Str(String),
    Bool(bool),
}

/// One comparison operator of the grammar.
#[derive(Debug, Clone, PartialEq)]
pub enum Cmp {
    Gt,
    Ge,
    Lt,
    Le,
    Eq,
    Ne,
}

impl Cmp {
    /// `a <op> b` for two numbers.
    fn holds(&self, a: f64, b: f64) -> bool {
        match self {
            Cmp::Gt => a > b,
            Cmp::Ge => a >= b,
            Cmp::Lt => a < b,
            Cmp::Le => a <= b,
            Cmp::Eq => a == b,
            Cmp::Ne => a != b,
        }
    }

    /// `actual <op> wanted` for an `attr` clause: numbers compare as numbers; strings and
    /// bools only with `==` and `!=`; two different kinds are never equal.
    fn holds_values(&self, actual: &Value, wanted: &Value) -> bool {
        match (actual, wanted) {
            (Value::Num(a), Value::Num(b)) => self.holds(*a, *b),
            (Value::Str(a), Value::Str(b)) => self.holds_str(a, b),
            (Value::Bool(a), Value::Bool(b)) => self.holds_bool(*a, *b),
            _ => false,
        }
    }

    fn holds_str(&self, a: &str, b: &str) -> bool {
        match self {
            Cmp::Eq => a == b,
            Cmp::Ne => a != b,
            _ => false, // Other operators not supported for strings
        }
    }

    fn holds_bool(&self, a: bool, b: bool) -> bool {
        match self {
            Cmp::Eq => a == b,
            Cmp::Ne => a != b,
            _ => false, // Other operators not supported for booleans
        }
    }
}

/// One clause. A `delta` threshold is an `f64`, never a `Value`.
#[derive(Debug, Clone, PartialEq)]
pub enum Clause {
    Changed { path: String },
    Delta { path: String, cmp: Cmp, value: f64 },
    Attr { path: String, cmp: Cmp, value: Value },
    Exists { path: String },
}

/// A compiled predicate. `paths` holds every path the clauses name, once each, in the
/// order they first appear. `cache` is the delta cache: written only by `seed` and
/// `commit_wake`, never by `eval`.
#[derive(Debug, Clone)]
pub struct Predicate {
    clauses: Vec<Clause>,
    paths: Vec<String>,
    cache: HashMap<String, f64>,
}

/// Compile `source` for a neuron whose scope is `scope`. Clauses are joined by `AND` only;
/// `OR`, trailing text or an unknown clause is an `Err`. A path outside the scope is an
/// `Err` here, at registration, never at fire time.
pub fn compile(source: &str, scope: &str) -> Result<Predicate, String> {
    let source = source.trim();
    if source.is_empty() {
        return Err("Empty predicate".to_string());
    }

    let mut clauses = Vec::new();
    let mut paths = Vec::new();
    let mut rest = source;

    while !rest.is_empty() {
        let (clause, new_rest) = parse_clause(rest, scope)?;
        rest = new_rest;
        clauses.push(clause);

        // Collect paths for deduplication
        match &clauses.last().unwrap() {
            Clause::Changed { path } => {
                if !paths.contains(path) {
                    paths.push(path.clone());
                }
            }
            Clause::Delta { path, .. } => {
                if !paths.contains(path) {
                    paths.push(path.clone());
                }
            }
            Clause::Attr { path, .. } => {
                if !paths.contains(path) {
                    paths.push(path.clone());
                }
            }
            Clause::Exists { path } => {
                if !paths.contains(path) {
                    paths.push(path.clone());
                }
            }
        }

        // Check for AND
        rest = rest.trim_start();
        if rest.starts_with("AND") {
            rest = rest[3..].trim_start();
            if rest.is_empty() {
                return Err("Trailing AND".to_string());
            }
        } else if !rest.is_empty() {
            return Err("Unknown clause or text after clause".to_string());
        }
    }

    Ok(Predicate {
        clauses,
        paths,
        cache: HashMap::new(),
    })
}

impl Predicate {
    /// Every path the clauses name, once each, in order.
    pub fn paths(&self) -> Vec<String> {
        self.paths.clone()
    }

    /// Fill the delta cache from the composed values at registration.
    pub fn seed(&mut self, values: &HashMap<String, Value>) {
        for path in &self.paths {
            if let Some(Value::Num(n)) = values.get(path) {
                self.cache.insert(path.clone(), *n);
            }
        }
    }

    /// True when every clause holds against `changed` (the event's paths) and `values`
    /// (the composed values of `paths()`; a missing key means no value). Reads the cache,
    /// never writes it.
    pub fn eval(&self, changed: &[String], values: &HashMap<String, Value>) -> bool {
        for clause in &self.clauses {
            match clause {
                Clause::Changed { path } => {
                    if !changed.contains(path) {
                        return false;
                    }
                }
                Clause::Delta { path, cmp, value } => {
                    let current = self.cache.get(path);
                    let wanted = values.get(path);

                    // If either current or wanted is missing, delta is false
                    match (current, wanted) {
                        (Some(&curr), Some(Value::Num(want))) => {
                            if !cmp.holds((curr - want).abs(), *value) {
                                return false;
                            }
                        }
                        _ => {
                            // No values to compare or not numeric; delta is false
                            return false;
                        }
                    }
                }
                Clause::Attr { path, cmp, value } => {
                    let wanted = values.get(path);
                    match wanted {
                        Some(actual) => {
                            if !cmp.holds_values(actual, value) {
                                return false;
                            }
                        }
                        None => {
                            // Missing attribute means no value, so attr clause is false
                            return false;
                        }
                    }
                }
                Clause::Exists { path } => {
                    if !values.contains_key(path) {
                        return false;
                    }
                }
            }
        }
        true
    }

    /// Move the delta cache to the values the wake saw.
    pub fn commit_wake(&mut self, values: &HashMap<String, Value>) {
        for (path, value) in values {
            if let Value::Num(n) = value {
                self.cache.insert(path.clone(), *n);
            }
        }
    }
}

/// True when `path` is inside `scope`: the prim part (before the first `.`) equals `scope`
/// or starts with `scope` followed by `/`. A plain `starts_with(scope)` would accept
/// `/Exchange/LookStateX` for the scope `/Exchange/LookState`.
fn in_scope(path: &str, scope: &str) -> bool {
    if path.starts_with(scope) {
        if path.len() == scope.len() {
            true
        } else {
            path.chars().nth(scope.len()) == Some('.')
        }
    } else {
        false
    }
}

// Each parser returns what it parsed and the input it did not consume, and the AND loop in
// `compile` continues from that rest. A parser that takes two `&str` names the lifetime of
// the one it returns a slice of.

/// One clause from the start of `s`, with the rest of `s` after it.
fn parse_clause<'a>(s: &'a str, scope: &str) -> Result<(Clause, &'a str), String> {
    let s = s.trim_start();
    if s.starts_with("changed(") {
        let (path, rest) = parse_path(&s[8..], scope)?;
        Ok((Clause::Changed { path }, rest))
    } else if s.starts_with("delta(") {
        let (path, rest) = parse_path(&s[6..], scope)?;
        let rest = rest.trim_start();
        let (cmp, rest) = parse_cmp(rest)?;
        let rest = rest.trim_start();
        let (value, rest) = parse_number(rest)?;
        Ok((Clause::Delta { path, cmp, value }, rest))
    } else if s.starts_with("attr(") {
        let (path, rest) = parse_path(&s[5..], scope)?;
        let rest = rest.trim_start();
        let (cmp, rest) = parse_cmp(rest)?;
        let rest = rest.trim_start();
        let (value, rest) = parse_literal(rest)?;
        Ok((Clause::Attr { path, cmp, value }, rest))
    } else if s.starts_with("exists(") {
        let (path, rest) = parse_path(&s[7..], scope)?;
        Ok((Clause::Exists { path }, rest))
    } else {
        Err("Unknown clause type".to_string())
    }
}

/// A path up to the closing `)`, checked with `in_scope`, with the rest after the `)`.
fn parse_path<'a>(s: &'a str, scope: &str) -> Result<(String, &'a str), String> {
    let end = s.find(')').ok_or("Missing closing parenthesis for path")?;
    let path = s[..end].trim();
    if !in_scope(path, scope) {
        return Err(format!("Path '{}' is not inside scope '{}'", path, scope));
    }
    Ok((path.to_string(), &s[end + 1..]))
}

/// A comparison operator, the two-character forms tried before `>` and `<`, with the rest
/// after it.
fn parse_cmp<'a>(s: &'a str) -> Result<(Cmp, &'a str), String> {
    let s = s.trim_start();
    if s.starts_with(">=") {
        Ok((Cmp::Ge, &s[2..]))
    } else if s.starts_with("<=") {
        Ok((Cmp::Le, &s[2..]))
    } else if s.starts_with("==") {
        Ok((Cmp::Eq, &s[2..]))
    } else if s.starts_with("!=") {
        Ok((Cmp::Ne, &s[2..]))
    } else if s.starts_with(">") {
        Ok((Cmp::Gt, &s[1..]))
    } else if s.starts_with("<") {
        Ok((Cmp::Lt, &s[1..]))
    } else {
        Err("Unknown comparison operator".to_string())
    }
}

/// A number parsed with `str::parse::<f64>`, also when it ends the input, with the rest
/// after it.
fn parse_number<'a>(s: &'a str) -> Result<(f64, &'a str), String> {
    let s = s.trim_start();
    // Find end of number (space or end of string)
    let end = s.find(|c: char| !c.is_ascii_digit() && c != '.' && c != '-' && c != '+')
        .unwrap_or(s.len());
    if end == 0 {
        return Err("Expected number".to_string());
    }
    let num_str = &s[..end];
    let num: f64 = num_str.parse().map_err(|_| "Invalid number".to_string())?;
    Ok((num, &s[end..]))
}

/// A literal: a number, a quoted string, or a bare token, with the rest after it.
fn parse_literal<'a>(s: &'a str) -> Result<(Value, &'a str), String> {
    let s = s.trim_start();
    if s.starts_with('"') {
        // Parse quoted string
        let end_quote = s[1..].find('"').ok_or("Missing closing quote for string")?;
        let str_val = &s[1..=end_quote];
        Ok((Value::Str(str_val.to_string()), &s[end_quote + 2..]))
    } else {
        // Try to parse as number first
        let end = s.find(|c: char| !c.is_ascii_digit() && c != '.' && c != '-' && c != '+')
            .unwrap_or(s.len());
        if end == 0 {
            Err("Expected literal".to_string())
        } else {
            let lit_str = &s[..end];
            if let Ok(num) = lit_str.parse::<f64>() {
                Ok((Value::Num(num), &s[end..]))
            } else {
                // Treat as bare token (string)
                Ok((Value::Str(lit_str.to_string()), &s[end..]))
            }
        }
    }
}
