//! The Python extension module `plexus._core`. The only file that names pyo3.

use std::collections::HashMap;

use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyString, PyTuple};

use crate::outcome::{Outcome, Reason, Status};
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

/// plexus._core.Outcome, the envelope every Plexus call returns. Frozen, and built only through
/// crate::outcome::Outcome::new, so a broken rule raises ValueError here and is written nowhere else.
#[pyclass(name = "Outcome", module = "plexus._core", frozen)]
struct PyOutcome {
    inner: Outcome<Py<PyAny>>,
}

#[pymethods]
impl PyOutcome {
    #[new]
    #[pyo3(signature = (status, payload = None, *, reason_code = None, reason = None, missing = Vec::new()))]
    fn new(
        status: &str,
        payload: Option<Py<PyAny>>,
        reason_code: Option<String>,
        reason: Option<String>,
        missing: Vec<String>,
    ) -> PyResult<Self> {
        let Some(parsed) = Status::from_name(status) else {
            return Err(PyValueError::new_err(format!(
                "status {status:?} is not \"ok\", \"unavailable\" or \"blocked\""
            )));
        };
        let reason = if reason_code.is_none() && reason.is_none() && missing.is_empty() {
            None
        } else {
            Some(Reason { code: reason_code.unwrap_or_default(), detail: reason.unwrap_or_default(), missing })
        };
        Outcome::new(parsed, payload, reason).map(|inner| PyOutcome { inner }).map_err(PyValueError::new_err)
    }

    #[getter]
    fn status(&self) -> &'static str {
        self.inner.status().name()
    }

    #[getter]
    fn ok(&self) -> bool {
        self.inner.is_ok()
    }

    #[getter]
    fn payload(&self, py: Python<'_>) -> Py<PyAny> {
        self.inner.payload().map_or_else(|| py.None(), |p| p.clone_ref(py))
    }

    #[getter]
    fn reason_code(&self) -> Option<&str> {
        self.inner.reason().map(|r| r.code.as_str())
    }

    #[getter]
    fn reason(&self) -> Option<&str> {
        self.inner.reason().map(|r| r.detail.as_str())
    }

    #[getter]
    fn missing<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        let names: &[String] = self.inner.reason().map_or(&[], |r| r.missing.as_slice());
        PyTuple::new(py, names)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let status = PyString::new(py, self.inner.status().name()).repr()?;
        let Some(r) = self.inner.reason() else {
            return Ok(format!("Outcome({status}, {})", self.payload(py).bind(py).repr()?));
        };
        let code = PyString::new(py, &r.code).repr()?;
        let detail = PyString::new(py, &r.detail).repr()?;
        let missing = if r.missing.is_empty() {
            String::new()
        } else {
            format!(", missing={}", self.missing(py)?.repr()?)
        };
        Ok(format!("Outcome({status}, reason_code={code}, reason={detail}{missing})"))
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("PredicateError", m.py().get_type::<PredicateError>())?;
    m.add_class::<PyPredicate>()?;
    m.add_class::<PyBudget>()?;
    m.add_class::<PyOutcome>()?;
    m.add_function(wrap_pyfunction!(compile_predicate, m)?)?;
    Ok(())
}
