"""
test_form_detector.py - Tests for the FormDetector module.
Verifies form detection from HTML and parsing of form elements.
"""

import pytest

from qa_ai.exploration.form_detector import (
    FormDetector,
    DetectedForm,
    DetectedInput,
    DetectedSelect,
    DetectedCheckbox,
    DetectedButton,
)


class TestFormDetector:
    def setup_method(self):
        self.detector = FormDetector()

    def test_detect_forms_from_html_empty(self):
        forms = self.detector.detect_forms_from_html("<html><body>No forms</body></html>")
        assert forms == []

    def test_detect_forms_from_html_simple_form(self):
        html = """
        <html><body>
        <form id="login" action="/login" method="POST">
            <input type="text" name="username" id="username" placeholder="Username" required>
            <input type="password" name="password" id="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms) == 1
        form = forms[0]
        assert form.form_id == "login"
        assert form.action == "/login"
        assert form.method == "POST"
        assert form.has_password is True
        assert len(form.inputs) == 2
        assert form.inputs[0].input_type == "text"
        assert form.inputs[0].name == "username"
        assert form.inputs[1].input_type == "password"
        assert len(form.buttons) == 1
        assert form.buttons[0].text == "Login"

    def test_detect_forms_from_html_with_select(self):
        html = """
        <html><body>
        <form>
            <select name="country" id="country">
                <option value="us">United States</option>
                <option value="uk">United Kingdom</option>
            </select>
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms) == 1
        assert len(forms[0].selects) == 1
        assert forms[0].selects[0].name == "country"

    def test_detect_forms_from_html_with_checkbox(self):
        html = """
        <html><body>
        <form>
            <input type="checkbox" name="agree" id="agree" value="yes">
            <input type="radio" name="plan" id="plan_free" value="free">
            <input type="radio" name="plan" id="plan_paid" value="paid">
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms) == 1
        assert len(forms[0].checkboxes) == 3
        assert forms[0].checkboxes[0].input_type == "checkbox"
        assert forms[0].checkboxes[1].input_type == "radio"

    def test_detect_forms_from_html_with_file_upload(self):
        html = """
        <html><body>
        <form>
            <input type="file" name="avatar" id="avatar">
            <input type="text" name="name">
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms) == 1
        assert forms[0].has_file_upload is True

    def test_detect_forms_from_html_multiple_forms(self):
        html = """
        <html><body>
        <form id="form1"><input type="text" name="a"></form>
        <form id="form2"><input type="email" name="b"></form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms) == 2

    def test_detect_forms_from_html_ignores_hidden_inputs(self):
        html = """
        <html><body>
        <form>
            <input type="hidden" name="csrf" value="token123">
            <input type="text" name="visible">
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms[0].inputs) == 1
        assert forms[0].inputs[0].name == "visible"

    def test_detect_forms_from_html_with_textarea(self):
        html = """
        <html><body>
        <form>
            <textarea name="comment" id="comment"></textarea>
        </form>
        </body></html>
        """
        forms = self.detector.detect_forms_from_html(html)
        assert len(forms[0].inputs) == 1
        assert forms[0].inputs[0].input_type == "textarea"


class TestDetectedForm:
    def test_defaults(self):
        form = DetectedForm()
        assert form.method == "GET"
        assert form.has_password is False
        assert form.has_file_upload is False
        assert form.inputs == []

    def test_to_dict(self):
        form = DetectedForm(
            form_id="test",
            action="/submit",
            method="POST",
            inputs=[DetectedInput(input_type="text", name="field1")],
            buttons=[DetectedButton(button_type="submit", text="Submit")],
            has_password=True,
        )
        data = form.to_dict()
        assert data["form_id"] == "test"
        assert data["has_password"] is True
        assert data["total_fields"] == 1
        assert len(data["inputs"]) == 1
        assert len(data["buttons"]) == 1


class TestDetectedInput:
    def test_to_dict(self):
        inp = DetectedInput(
            input_type="email",
            name="email",
            id="email-field",
            placeholder="Enter email",
            label="Email Address",
            required=True,
        )
        data = inp.to_dict()
        assert data["input_type"] == "email"
        assert data["required"] is True


class TestDetectedSelect:
    def test_to_dict(self):
        sel = DetectedSelect(name="country", options=["US", "UK"])
        data = sel.to_dict()
        assert data["name"] == "country"
        assert "US" in data["options"]


class TestDetectedCheckbox:
    def test_to_dict(self):
        cb = DetectedCheckbox(input_type="checkbox", name="agree", checked=True)
        data = cb.to_dict()
        assert data["input_type"] == "checkbox"
        assert data["checked"] is True


class TestDetectedButton:
    def test_to_dict(self):
        btn = DetectedButton(button_type="submit", text="Save", disabled=False)
        data = btn.to_dict()
        assert data["button_type"] == "submit"
        assert data["text"] == "Save"
