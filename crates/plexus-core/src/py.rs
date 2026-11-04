//! The Python extension module `plexus._core`. The only file that names pyo3.

use std::collections::HashMap;

use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::predicate::Value;

create_exception!(plexus._core, PredicateError, PyValueError);

/// dict[str, float | int | bool | str | None] -> Rust values. None and other types are left out.
fn to_values(d: &Bound<'_, PyDict>) -> PyResult<HashMap<String, Value>> {
    let mut out = HashMap::new();
    for (k, v) in d.iter() {
        let key: String = k.extract()?;
        let val = if let Ok(b) = v.extract::<bool>() {
            Value::Bool(b) // bool first: True also extracts as 1.0
        } else if let Ok(x) = v.extract::<f64>() {
            Value::Num(x)
        } else if let Ok(s) = v.extract::<String>() {
            Value::Str(s)
        } else {
            continue;
        };
        out.insert(key, val);
    }
    Ok(out)
}

#[pyclass(name = "Predicate")]
struct PyPredicate {
    inner: crate::predicate::Predicate,
}

#[pymethods]
impl PyPredicate {
    fn paths(&self) -> Vec<String> {
        self.inner.paths()
    }
    fn seed(&mut self, values: &Bound<'_, PyDict>) -> PyResult<()> {
        self.inner.seed(&to_values(values)?);
        Ok(())
    }
    fn eval(&self, changed: Vec<String>, values: &Bound<'_, PyDict>) -> PyResult<bool> {
        Ok(self.inner.eval(&changed, &to_values(values)?))
    }
    fn commit_wake(&mut self, values: &Bound<'_, PyDict>) -> PyResult<()> {
        self.inner.commit_wake(&to_values(values)?);
        Ok(())
    }
}

#[pyfunction]
fn compile_predicate(source: &str, scope: &str) -> PyResult<PyPredicate> {
    crate::predicate::compile(source, scope)
        .map(|inner| PyPredicate { inner })
        .map_err(PredicateError::new_err)
}

#[pyclass(name = "Budget")]
struct PyBudget {
    inner: crate::budget::Budget,
}

#[pymethods]
impl PyBudget {
    #[new]
    fn new(wakes: u32, window_s: f64) -> Self {
        PyBudget { inner: crate::budget::Budget::new(wakes, window_s) }
    }
    fn peek(&self, now: f64) -> &'static str {
        self.inner.peek(now)
    }
    fn admit(&mut self, now: f64) -> &'static str {
        self.inner.admit(now)
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("PredicateError", m.py().get_type::<PredicateError>())?;
    m.add_class::<PyPredicate>()?;
    m.add_class::<PyBudget>()?;
    m.add_function(wrap_pyfunction!(compile_predicate, m)?)?;
    Ok(())
}
