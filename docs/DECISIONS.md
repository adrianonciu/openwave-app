ADR-001: Backend framework
## ADR-001: FastAPI as backend framework

Date: 2026-03-06

Context

The backend requires a lightweight API layer capable of serving
mobile clients and handling asynchronous workflows such as
RSS ingestion and AI processing.

Decision

Use FastAPI as the backend framework.

Reason

FastAPI provides:
- high performance
- automatic OpenAPI documentation
- simple async support
- minimal boilerplate

Consequences

API endpoints are implemented using FastAPI.
Swagger documentation is automatically available at /docs.
ADR-002: Flutter mobile client
## ADR-002: Flutter as mobile framework

Date: 2026-03-06

Context

The product must support Android and iOS with a single codebase.

Decision

Use Flutter for the mobile application.

Reason

Flutter enables:
- single codebase
- fast iteration
- strong UI control
- good performance for audio apps

Consequences

Mobile client resides in flutter_app/.
ADR-003: Segment-based architecture

Aceasta este cea mai importantă decizie pentru produs.

## ADR-003: Segment-based audio architecture

Date: 2026-03-07

Context

The product generates dynamic listening sessions rather than
static audio files.

Decision

Use a segment-based architecture:

Article → Segment → Session → Audio playlist

Reason

Segments allow:
- dynamic session assembly
- commute-length briefings
- insertion of opposing viewpoints
- fact-check segments
- flexible audio playback

Consequences

Future services will generate Segment objects before building
sessions or briefings.
ADR-004: Repository structure
## ADR-004: Standard repository structure

Date: 2026-03-06

Decision

Use a fixed repository structure:

backend/
flutter_app/
docs/

Reason

Prevents structural drift and keeps the project predictable
for both developers and AI agents.

Consequences

Agents must not create alternative folders such as:
mobile/, frontend/, client/.