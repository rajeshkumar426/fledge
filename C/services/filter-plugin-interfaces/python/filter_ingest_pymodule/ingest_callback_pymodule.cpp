/*
 * Fledge python module for filter plugin ingest callback
 *
 * Copyright (c) 2019 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Massimiliano Pinto
 */

#include <reading.h>
#include <reading_set.h>
#include <logger.h>
#include <Python.h>
#include <vector>

extern "C" {

typedef void (*INGEST_CB_DATA)(void *, ReadingSet *);
extern std::vector<Reading *>* Py2C_getReadings(PyObject *polledData);

static void filter_plugin_ingest_fn(PyObject *ingest_callback,
				    PyObject *ingest_obj_ref_data,
				    PyObject *readingsObj);

static PyObject *IngestError;

/**
 * Implementation of data ingest into filters chain
 *
 * @param    self       The python module object
 * @param    args       Input arguments
 * @return              PyObject of None type
 */
static PyObject *filter_ingest_callback(PyObject *self, PyObject *args)
{
	PyObject *readingList;
	PyObject *callback;
	PyObject *ingestData;

	if (!PyArg_ParseTuple(args,
			      "OOO",
			      &callback,
			      &ingestData,
			      &readingList))
	{
		Logger::getLogger()->error("Cannot parse input arguments "
					   "of filter_ingest_callback C API module");
		return NULL;
	}

	// Invoke callback routine
	filter_plugin_ingest_fn(callback,
				ingestData,
				readingList);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef FilterIngestMethods[] = {
	{
		"filter_ingest_callback",
		filter_ingest_callback,
		METH_VARARGS,
		"Invoke filter ingest callback"
	},
	{NULL, NULL, 0, NULL}    /* Sentinel */
};

static struct PyModuleDef filterIngestmodule = {
	PyModuleDef_HEAD_INIT,
	"filter_ingest",   /* name of module */
	NULL, 		/* module documentation, may be NULL */
	-1,       	/* size of per-interpreter state of the module,
	             or -1 if the module keeps state in global variables. */
	FilterIngestMethods
};

/**
 * Init the C API Python module
 */
PyMODINIT_FUNC
PyInit_filter_ingest(void)
{	
	PyObject *m;

	m = PyModule_Create(&filterIngestmodule);
	if (m == NULL)
	{
		Logger::getLogger()->fatal("Cannot initialise filter_ingest C API module");
		return NULL;
	}

	IngestError = PyErr_NewException("ingest.error", NULL, NULL);
	Py_INCREF(IngestError);
	PyModule_AddObject(m, "error", IngestError);

	return m;
}

/**
 * Ingest data into filters chain
 *
 * @param    ingest_callback            The callback routine
 * @param    ingest_obj_ref_data        Object parameter for callback routine
 * @param    readingsObj                Readongs data as PyObject
 */
void filter_plugin_ingest_fn(PyObject *ingest_callback,
			     PyObject *ingest_obj_ref_data,
			     PyObject *readingsObj)
{
	if (ingest_callback == NULL ||
	    ingest_obj_ref_data == NULL ||
	    readingsObj == NULL)
	{
		Logger::getLogger()->error("PyC interface error: "
					   "filter_plugin_ingest_fn: "
					   "filter_ingest_callback=%p, "
					   "ingest_obj_ref_data=%p, "
					   "readingsObj=%p",
					   ingest_callback,
					   ingest_obj_ref_data,
					   readingsObj);
		return;
	}

	std::vector<Reading *> *vec = NULL;

	// Check we have a list of readings
	if (PyList_Check(readingsObj))
	{
		// Get vector of Readings from Python object
		vec =  Py2C_getReadings(readingsObj);
	}
	else
	{
		Logger::getLogger()->error("Filter did not return a Python List "
					   "but object type %s",
					   Py_TYPE(readingsObj)->tp_name);
	}

	if (vec)
	{
		// Get callback pointer
		INGEST_CB_DATA cb = (INGEST_CB_DATA) PyCapsule_GetPointer(ingest_callback, NULL);
		// Get ingest object parameter
		void *data = PyCapsule_GetPointer(ingest_obj_ref_data, NULL);

		// Create ReadingSet object
		ReadingSet *newData = new ReadingSet(vec);

		// Delete vector object
		delete vec;

		// Invoke callback method for ReadingSet filter ingestion
		(*cb)(data, newData);
	}
	else
	{
		Logger::getLogger()->error("PyC interface: plugin_ingest_fn: "
					   "Py2C_getReadings() returned NULL");
	}
}
}; // end of extern "C" block
