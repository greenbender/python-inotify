/*
 * Copyright (c) 2004 Novell, Inc.
 * Copyright (c) 2005 Manuel Amador <rudd-o@rudd-o.com>
 * Copyright (c) 2009-2011 Forest Bond <forest@alittletooquiet.net>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */

/*
 * Minor modifications 2012-05-21 Byron Platt <byron.platt@gmail.com>
 */

#include <Python.h>
#include <sys/select.h>
#include <sys/inotify.h>

#define BUF_LENGTH 4096

static PyObject *
binding_init(PyObject *self, PyObject *args)
{
    int fd;

    Py_BEGIN_ALLOW_THREADS;
    fd = inotify_init();
    Py_END_ALLOW_THREADS;

    if (fd == -1)
        return PyErr_SetFromErrno(PyExc_IOError);

    return Py_BuildValue("i", fd);
}

static PyObject *
binding_add_watch(PyObject *self, PyObject *args)
{
    int fd;
    char *path;
    uint32_t mask;

    int wd;

    mask = IN_ALL_EVENTS;

    if (!PyArg_ParseTuple(args, "is|i", &fd, &path, &mask))
        return NULL;

    Py_BEGIN_ALLOW_THREADS;
    wd = inotify_add_watch(fd, (const char *)path, mask);
    Py_END_ALLOW_THREADS;

    if ( wd == -1)
        return PyErr_SetFromErrno(PyExc_IOError);

    return Py_BuildValue("i", wd);
}

static PyObject *
binding_rm_watch(PyObject *self, PyObject *args)
{
    int fd;
    int wd;

    int result;

    if (!PyArg_ParseTuple(args, "ii", &fd, &wd))
        return NULL;

    Py_BEGIN_ALLOW_THREADS;
    result = inotify_rm_watch(fd, wd);
    Py_END_ALLOW_THREADS;

    if (result == -1)
        return PyErr_SetFromErrno(PyExc_IOError);

    Py_RETURN_NONE;
}
static PyObject *
binding_get_events(PyObject *self, PyObject *args)
{
    int fd;
    PyObject *timeout_o = NULL;

    double timeout_d;
    struct timeval timeout_s;
    struct timeval *timeout_p = NULL;
    fd_set fds;
    int result;
    char buffer[BUF_LENGTH];
    int length;
    struct inotify_event *event_p;
    PyObject *event_o = NULL;
    PyObject *events = NULL;

    if (!PyArg_ParseTuple(args, "i|O", &fd, &timeout_o))
        return NULL;

    if (timeout_o != Py_None)
    {
        timeout_d = PyFloat_AsDouble(timeout_o);
        if (PyErr_Occurred() != NULL)
            return NULL;

        timeout_s.tv_sec = (int)timeout_d;
        timeout_s.tv_usec = (int)(1000000.0 * (timeout_d - (double)timeout_s.tv_sec));
        timeout_p = &timeout_s;
    } 

    FD_ZERO(&fds);
    FD_SET(fd, &fds);

    Py_BEGIN_ALLOW_THREADS;
    result = select(fd + 1, &fds, NULL, NULL, timeout_p);
    Py_END_ALLOW_THREADS;

    if (result == -1)
        return PyErr_SetFromErrno(PyExc_IOError);

    if (result == 0)
        return PyList_New(0);

    Py_BEGIN_ALLOW_THREADS;
    length = read(fd, buffer, sizeof(buffer));
    Py_END_ALLOW_THREADS;

    if (length == -1)
        return PyErr_SetFromErrno(PyExc_IOError);

    if (length == 0)
    {
        PyErr_SetString(PyExc_IOError, "event buffer too small");
        return NULL;
    }

    events = PyList_New(0);

    event_p = (struct inotify_event *)buffer;
    while ((char *)event_p < buffer + length)
    {
        if (event_p->len)
            event_o = Py_BuildValue("iiis", event_p->wd, event_p->mask,
                event_p->cookie, event_p->name);
        else
            event_o = Py_BuildValue("iiis", event_p->wd, event_p->mask,
                event_p->cookie, "");
        
        if (PyList_Append(events, event_o) == -1)
        {
            Py_DECREF(event_o);
            Py_DECREF(events);
            return NULL;
        }

        Py_DECREF(event_o);

        event_p = (struct inotify_event *)((char *)(event_p + 1) + event_p->len);
    }

    return events;
}

static PyMethodDef
bindingMethods[] = {
    {"init",       binding_init,       METH_VARARGS, NULL},
    {"add_watch",  binding_add_watch,  METH_VARARGS, NULL},
    {"rm_watch",   binding_rm_watch,   METH_VARARGS, NULL},
    {"get_events", binding_get_events, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initbinding(void)
{
    PyObject* module = Py_InitModule("inotify.binding",  bindingMethods);

    if (module == NULL)
        return;
    
    PyModule_AddIntMacro(module, IN_ACCESS);
    PyModule_AddIntMacro(module, IN_MODIFY);
    PyModule_AddIntMacro(module, IN_ATTRIB);
    PyModule_AddIntMacro(module, IN_CLOSE_WRITE);
    PyModule_AddIntMacro(module, IN_CLOSE_NOWRITE);
    PyModule_AddIntMacro(module, IN_CLOSE);
    PyModule_AddIntMacro(module, IN_OPEN);
    PyModule_AddIntMacro(module, IN_MOVED_FROM);
    PyModule_AddIntMacro(module, IN_MOVED_TO);
    PyModule_AddIntMacro(module, IN_MOVE);
    PyModule_AddIntMacro(module, IN_CREATE);
    PyModule_AddIntMacro(module, IN_DELETE);
    PyModule_AddIntMacro(module, IN_DELETE_SELF);
    PyModule_AddIntMacro(module, IN_MOVE_SELF);
    PyModule_AddIntMacro(module, IN_UNMOUNT);
    PyModule_AddIntMacro(module, IN_Q_OVERFLOW);
    PyModule_AddIntMacro(module, IN_IGNORED);
    PyModule_AddIntMacro(module, IN_ONLYDIR);
    PyModule_AddIntMacro(module, IN_DONT_FOLLOW);
    PyModule_AddIntMacro(module, IN_MASK_ADD);
    PyModule_AddIntMacro(module, IN_ISDIR);
    PyModule_AddIntMacro(module, IN_ONESHOT);
    PyModule_AddIntMacro(module, IN_ALL_EVENTS);
}
