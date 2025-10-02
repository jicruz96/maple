import { DateTime } from "luxon"
import Link from "next/link"
import { useTranslation } from "next-i18next"
import styled from "styled-components"
import { Card, Badge } from "../../bootstrap"
import { Highlight } from "react-instantsearch"
import { timeZone } from "../../db/events"
import { HearingHitData } from "./HearingSearch"

type HearingHitProps = {
  hit: HearingHitData
  loading: boolean
}

const StyledCard = styled(Card)`
  border: none;
  border-radius: 4px;
  margin-bottom: 0.75rem;
  overflow: hidden;
  cursor: pointer;
  outline-color: var(--bs-blue);
  outline-style: solid;
  outline-width: 0;
  transition: outline-width 0.1s;

  font-size: 0.85rem;

  &:hover {
    outline-width: 2px;
  }

  &:active {
    outline-width: 4px;
  }

  .card-body {
    padding: 0.85rem 1rem;
  }
`

const SectionLabel = styled.span`
  color: var(--bs-blue);
  font-weight: 600;
  margin-right: 0.5rem;
`

const formatSchedule = (startsAt: number) => {
  const dt = DateTime.fromMillis(startsAt, { zone: timeZone })
  return {
    date: dt.toFormat("MMMM d, yyyy"),
    time: dt.toFormat("h:mm a")
  }
}

export const HearingHit = ({ hit, loading }: HearingHitProps) => {
  const { t } = useTranslation(["search", "hearing"])
  const schedule = formatSchedule(hit.startsAt)
  const chairNames = hit.chairNames ?? []
  const topics = hit.agendaTopics ?? []

  return (
    <Link href={`/hearing/${hit.eventId}`} legacyBehavior>
      <a style={{ all: "unset" }} className="w-100">
        <StyledCard>
          <Card.Body className="bg-white">
            <div className="d-flex flex-column gap-2">
              <div className="d-flex flex-wrap gap-2 align-items-center justify-content-between">
                <div className="d-flex flex-column">
                  <span className="text-uppercase fw-semibold text-secondary">
                    {schedule.date}
                  </span>
                  <span className="text-secondary">{schedule.time}</span>
                </div>
                {hit.hasVideo ? (
                  <Badge bg="success" pill>
                    {t("video_available")}
                  </Badge>
                ) : null}
              </div>

              <div>
                <Card.Title as="h6" className="mb-1">
                  <Highlight attribute="title" hit={hit} />
                </Card.Title>
                {hit.description ? (
                  <p className="mb-0 text-muted">
                    <Highlight attribute="description" hit={hit} />
                  </p>
                ) : null}
              </div>

              {hit.locationName || hit.locationCity ? (
                <div>
                  <SectionLabel>{t("location_label")}</SectionLabel>
                  <span>
                    {hit.locationName ?? hit.locationCity}
                    {hit.locationName && hit.locationCity
                      ? ` · ${hit.locationCity}`
                      : ""}
                  </span>
                </div>
              ) : null}

              {chairNames.length ? (
                <div>
                  <SectionLabel>{t("chairs", { ns: "hearing" })}</SectionLabel>
                  <span>
                    {chairNames.join(", ")}
                    {loading ? ` (${t("loading_chairs")})` : ""}
                  </span>
                </div>
              ) : loading && chairNames.length ? (
                <div className="text-secondary">
                  <SectionLabel>{t("chairs", { ns: "hearing" })}</SectionLabel>
                  <span>{t("loading_chairs")}</span>
                </div>
              ) : null}

              {topics.length ? (
                <div>
                  <SectionLabel>{t("agenda_label")}</SectionLabel>
                  <span>{topics.join(", ")}</span>
                </div>
              ) : null}

              {hit.billNumbers && hit.billNumbers.length ? (
                <div>
                  <SectionLabel>{t("bills_label")}</SectionLabel>
                  <span>{hit.billNumbers.join(", ")}</span>
                </div>
              ) : null}
            </div>
          </Card.Body>
        </StyledCard>
      </a>
    </Link>
  )
}
