#include <Python.h>
#include <vector>

static PyObject *parse_str(PyObject *self, PyObject *args);
static PyMethodDef moduleMethods[] = {
    {"parse_str", parse_str, METH_O, "parse linecard string"},
    {NULL, NULL, 0, NULL}};
static struct PyModuleDef linecard_parsing = PyModuleDef{
    PyModuleDef_HEAD_INIT,
    "linecard_parsing",
    "I hope it's faster than regular expression",
    -1,
    moduleMethods,
};

PyMODINIT_FUNC PyInit_linecard_parsing(void) {
  return PyModule_Create(&linecard_parsing);
}

static char *substr(const char *str, long start, long end) {
  long l = end - start;
  char *result = new char[l + 1];
  memcpy(result, str + start, l);
  result[l] = '\0';
  return result;
}

static bool startswith(const char *str, const char *prefix) {
  for (long i = 0; prefix[i] != '\0'; ++i)
    if (str[i] != prefix[i])
      return false;
  return true;
}

struct Tag {
  const char name;
  const char *value;
  const long l;
  const long r;
  const bool dynamic;
};

struct ParsedText {
  char *text;
  std::vector<Tag> args;
  ParsedText(const char *rawtext) {
    long length = 1;
    char tagName = '\0';
    long tagL, tagArgsL;
    long rawChecked = 0;
    long rawL, rawR;
    bool inRaw;
    long i;
    long iTmp;
    for (i = 0; rawtext[i] != '\0'; ++i) {
      if (i > rawChecked and rawtext[i] == '{') {
        inRaw = false;
        rawL = i;
        for (iTmp = i; rawtext[iTmp] != '\0'; iTmp++) {
          if (rawtext[iTmp] == '}') {
            rawR = iTmp;
            inRaw = true;
          } else if (inRaw and rawtext[iTmp] == '{') {
            i = rawR;
            rawChecked = iTmp - 1;
            args.push_back(
                Tag{'r', substr(rawtext, rawL + 1, rawR), rawL, rawR, true});
            length -= rawR - rawL - 1;
            goto next;
          }
        }
        if (inRaw) {
          i = rawR;
          rawChecked = iTmp;
          args.push_back(
              Tag{'r', substr(rawtext, rawL + 1, rawR), rawL, rawR, true});
          length -= rawR - rawL - 1;
        }
      } else if (rawtext[i] == '[') {
        const char *start_ptr = rawtext + i + 1;
        if (startswith(start_ptr, "center]")) {
          args.push_back(Tag{'a', "center", i, i += 7, false});
          length -= 6;
        } else if (startswith(start_ptr, "left]")) {
          args.push_back(Tag{'a', "left", i, i += 5, false});
          length -= 4;
        } else if (startswith(start_ptr, "right]")) {
          args.push_back(Tag{'a', "right", i, i += 6, false});
          length -= 5;
        } else if (startswith(start_ptr, "pixel ")) {
          tagL = i;
          tagArgsL = i += 7;
          tagName = 'a';
        } else if (startswith(start_ptr, "style ")) {
          tagL = i;
          tagArgsL = i += 7;
          tagName = 's';
        } else if (startswith(start_ptr, "font ")) {
          tagL = i;
          i += 6;
          tagArgsL = i;
          tagName = 'f';
        } else if (startswith(start_ptr, "nowrap]")) {
          args.push_back(Tag{'t', "nowrap", i, i += 7, false});
          length -= 6;
        } else if (startswith(start_ptr, "passport]")) {
          args.push_back(Tag{'t', "passport", i, i += 9, false});
          length -= 8;
        } else if (startswith(start_ptr, "autowrap]")) {
          args.push_back(Tag{'t', "autowrap", i, i += 9, false});
          length -= 8;
        } else if (startswith(start_ptr, "noautowrap]")) {
          args.push_back(Tag{'t', "noautowrap", i, i += 11, false});
          length -= 10;
        }
      } else if (tagName != '\0' and rawtext[i] == ']') {
        args.push_back(
            Tag{tagName, substr(rawtext, tagArgsL, i), tagL, i, true});
        tagName = '\0';
        length -= i - tagL - 1;
      }
    next:;
    }
    length += i;
    iTmp = 0;
    text = new char[length];
    char *ptrText = text;
    for (auto &tag : args) {
      memcpy(ptrText, rawtext + iTmp, tag.l - iTmp);
      ptrText += (tag.l - iTmp);
      *ptrText++ = '{';
      *ptrText++ = '}';
      iTmp = tag.r + 1;
    }
    memcpy(ptrText, rawtext + iTmp, i - iTmp);
    ptrText += i - iTmp;
    *ptrText = '\0';
  }
  ~ParsedText() {
    delete[] text;
    for (auto &tag : args) {
      if (tag.dynamic) {
        delete[] tag.value;
      }
    }
  }
};

static PyObject *parse_str(PyObject *self, PyObject *args) {
  if (!PyUnicode_Check(args)) {
    PyErr_SetString(PyExc_TypeError, "Expected a string argument");
    return NULL;
  }
  const char *input_string = PyUnicode_AsUTF8(args);
  if (input_string == NULL) {
    return NULL;
  }
  ParsedText result = ParsedText(input_string);
  PyObject *result_list = PyList_New(result.args.size());
  long i = 0;
  for (auto &tag : result.args) {
    PyObject *tag_tuple = PyTuple_New(2);
    PyTuple_SetItem(tag_tuple, 0, PyBytes_FromStringAndSize(&tag.name, 1));
    PyTuple_SetItem(tag_tuple, 1, PyUnicode_FromString(tag.value));
    PyList_SetItem(result_list, i++, tag_tuple);
  }
  PyObject *result_tuple =
      PyTuple_Pack(2, PyUnicode_FromString(result.text), result_list);
  return result_tuple;
}
