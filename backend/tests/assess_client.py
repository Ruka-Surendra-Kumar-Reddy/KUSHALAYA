"""Step 1 of every assessment (client details + home location) for tests that submit."""

CLIENT = {
    "first_name": "Lakshmi", "last_name": "Rao", "phone": "9876500001", "gender": "female",
    "date_of_birth": "1948-05-01", "address": "Plot 5, Uppal", "area": "Uppal", "city": "Hyderabad",
    "pincode": "500039", "emergency_contact_name": "Arjun", "emergency_contact_phone": "9876500002",
}


def confirm_client(client, headers, job_id, portal: bool = False):
    base = f"/api/v1/caregiver-portal/jobs/{job_id}" if portal else f"/api/v1/jobs/{job_id}"
    res = client.put(f"{base}/assessment/client", headers=headers,
                     json={"details": CLIENT, "location": {"mode": "auto", "latitude": 17.40, "longitude": 78.56}})
    assert res.status_code == 200, res.text
    return res.json()
