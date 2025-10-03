import Link from "next/link"
import { useTranslation } from "next-i18next"
import styled from "styled-components"
import { Card, Badge } from "../../bootstrap"
import { Highlight } from "react-instantsearch"
import { HearingHitData } from "./HearingSearch"

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

export const HearingHit = ({ hit }: { hit: HearingHitData }) => {
  const { t } = useTranslation(["search", "hearing"])
  const startsAt = new Date(hit.startsAt)
  const scheduleDate = t("schedule_date", { ns: "hearing", date: startsAt })
  const scheduleTime = t("schedule_time", { ns: "hearing", date: startsAt })
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
                    {scheduleDate}
                  </span>
                  <span className="text-secondary">{scheduleTime}</span>
                </div>
                {hit.hasVideo ? (
                  <Badge bg="success" pill>
                    {t("video_available", { ns: "search" })}
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
                  <SectionLabel>
                    {t("location_label", { ns: "search" })}
                  </SectionLabel>
                  <span>
                    {hit.locationName ?? hit.locationCity}
                    {hit.locationName && hit.locationCity
                      ? ` · ${hit.locationCity}`
                      : ""}
                  </span>
                </div>
              ) : null}

              {chairNames.length && (
                <div className="d-flex align-items-center gap-2">
                  <SectionLabel>{t("chairs", { ns: "hearing" })}</SectionLabel>
                  {<span>{chairNames.join(", ")}</span>}
                </div>
              )}

              {topics.length ? (
                <div>
                  <SectionLabel>
                    {t("agenda_label", { ns: "search" })}
                  </SectionLabel>
                  <span>{topics.join(", ")}</span>
                </div>
              ) : null}

              {hit.billNumbers && hit.billNumbers.length ? (
                <div>
                  <SectionLabel>
                    {t("bills_label", { ns: "search" })}
                  </SectionLabel>
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
