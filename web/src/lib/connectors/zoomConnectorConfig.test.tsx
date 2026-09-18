import { render, screen } from "@tests/setup/test-utils";
import { Formik } from "formik";
import { RenderField } from "@/app/admin/connectors/[connector]/pages/FieldRendering";
import {
  connectorConfigs,
  createConnectorInitialValues,
} from "@/lib/connectors/connectors";
import { ValidSources } from "@/lib/types";

function ZoomForm() {
  const config = connectorConfigs.zoom;
  return (
    <Formik
      initialValues={createConnectorInitialValues(ValidSources.Zoom)}
      onSubmit={() => {}}
    >
      {({ values }) => (
        <>
          {[...config.values, ...config.advanced_values].map((field) => (
            <RenderField
              key={field.name}
              field={field}
              values={values}
              connector={ValidSources.Zoom}
              currentCredential={null}
            />
          ))}
        </>
      )}
    </Formik>
  );
}

test("every discovery mechanism is on the form at once", () => {
  render(<ZoomForm />);

  for (const label of [
    "Meeting IDs",
    "Webinar IDs",
    "Host Emails",
    "Zoom Group ID",
  ]) {
    expect(screen.getByText(label)).toBeInTheDocument();
  }
});

test("meetings and webinars are both included until the admin unticks one", () => {
  const values = createConnectorInitialValues(ValidSources.Zoom);

  expect(values.include_meetings).toBe(true);
  expect(values.include_webinars).toBe(true);
});

test("the form posts the names the connector takes", () => {
  const names = connectorConfigs.zoom.values.map((field) => field.name);

  expect(names).toEqual([
    "meeting_ids",
    "webinar_ids",
    "host_emails",
    "group_id",
    "include_meetings",
    "include_webinars",
    "plan_tier",
  ]);
});

test("the plan select offers exactly the tiers the backend parses", () => {
  render(<ZoomForm />);

  const plan = screen.getByRole("combobox");
  expect(
    [...plan.querySelectorAll("option")].map((option) => option.value)
  ).toEqual(["", "pro", "business_plus"]);
});

test("the rate limit share is an advanced number field", () => {
  render(<ZoomForm />);

  const rateLimit = screen.getByRole("spinbutton");
  expect(rateLimit).toHaveAttribute("name", "rate_limit_percent");
});
