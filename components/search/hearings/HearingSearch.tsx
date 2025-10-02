import { Hit } from "instantsearch.js"
import { RefinementListItem } from "instantsearch.js/es/connectors/refinement-list/connectRefinementList"
import { TFunction, useTranslation } from "next-i18next"
import singletonRouter from "next/router"
import { FC, useCallback, useMemo } from "react"
import {
  CurrentRefinements,
  Hits,
  InstantSearch,
  Pagination,
  SearchBox
} from "react-instantsearch"
import { createInstantSearchRouterNext } from "react-instantsearch-router-nextjs"
import styled from "styled-components"
import TypesenseInstantSearchAdapter from "typesense-instantsearch-adapter"
import { Col, Container, Row, Spinner } from "../../bootstrap"
import { useMemberSearch } from "../../db/members"
import { NoResults } from "../NoResults"
import { ResultCount } from "../ResultCount"
import { SearchContainer } from "../SearchContainer"
import { SearchErrorBoundary } from "../SearchErrorBoundary"
import { SortBy, SortByWithConfigurationItem } from "../SortBy"
import {
  getServerConfig,
  SearchStatus,
  useSearchStatus,
  VirtualFilters
} from "../common"
import { pathToSearchState, searchStateToUrl } from "../routingHelpers"
import { useRefinements } from "../useRefinements"
import { HearingHit } from "./HearingHit"

const searchClient = new TypesenseInstantSearchAdapter({
  server: getServerConfig(),
  additionalSearchParameters: {
    query_by:
      "title,description,agendaTopics,billNumbers,chairNames,locationName,locationCity",
    sort_by: "startsAt:asc"
  }
}).searchClient

/* carbon copy of type in functions/src/hearings/search.ts */
export type HearingSearchRecord = {
  id: string
  eventId: number
  title: string
  description?: string
  startsAt: number
  month: string
  year: number
  committeeCode?: string
  committeeName?: string
  locationName?: string
  locationCity?: string
  chairNames?: string[]
  agendaTopics?: string[]
  billNumbers?: string[]
  hasVideo: boolean
}

export type HearingHitData = Hit<HearingSearchRecord>

export const HearingSearch = () => {
  const { t } = useTranslation("search")
  const { loading } = useMemberSearch()

  const refinements = useHearingRefinements()
  const sortItems = useHearingSort()
  const status = useSearchStatus()

  const HearingHitComponent: FC<{ hit: HearingHitData }> = useCallback(
    ({ hit }) => <HearingHit hit={hit} loading={loading} />,
    [loading]
  )

  return (
    <SearchErrorBoundary>
      <InstantSearch
        indexName={sortItems[0].value}
        searchClient={searchClient}
        routing={{
          router: createInstantSearchRouterNext({
            singletonRouter,
            routerOptions: {
              cleanUrlOnDispose: false,
              createURL: args => searchStateToUrl(args),
              parseURL: args => pathToSearchState(args)
            }
          })
        }}
        future={{ preserveSharedStateOnUnmount: true }}
      >
        <VirtualFilters type="hearing" />
        <Layout
          refinements={refinements.options}
          filterToggle={refinements.show}
          status={status}
          sortItems={sortItems}
          HearingHitComponent={HearingHitComponent}
          searchPlaceholder={t("search_placeholder_hearings")}
        />
      </InstantSearch>
    </SearchErrorBoundary>
  )
}

type LayoutProps = {
  refinements: React.ReactNode
  filterToggle: React.ReactNode
  status: SearchStatus
  sortItems: ReturnType<typeof useHearingSort>
  HearingHitComponent: FC<{ hit: HearingHitData }>
  searchPlaceholder: string
}

const Layout: FC<LayoutProps> = ({
  refinements,
  filterToggle,
  status,
  sortItems,
  HearingHitComponent,
  searchPlaceholder
}) => {
  const { t } = useTranslation("search")

  return (
    <SearchContainer>
      <Row>
        <SearchBox placeholder={searchPlaceholder} className="mt-2 mb-3" />
      </Row>
      <Row>
        <Col xs={12} lg={3} className="mb-3 mb-lg-0">
          {refinements}
        </Col>
        <Col className="d-flex flex-column">
          <div className="d-flex flex-wrap gap-2 align-items-center mt-1 mb-2">
            <ResultCount className="flex-grow-1" />
            <SortBy items={sortItems} />
            {filterToggle}
          </div>
          <CurrentRefinements className="mt-2 mb-3" />
          <Results
            status={status}
            t={t}
            HearingHitComponent={HearingHitComponent}
          />
          <Pagination className="mx-auto mt-3 mb-4" />
        </Col>
      </Row>
    </SearchContainer>
  )
}

type ResultsProps = {
  status: SearchStatus
  HearingHitComponent: FC<{ hit: HearingHitData }>
  t: TFunction
}

const StyledLoadingContainer = styled(Container)`
  background-color: white;
  display: flex;
  height: 300px;
  justify-content: center;
  align-items: center;
`

const Results: FC<ResultsProps> = ({ status, HearingHitComponent, t }) => {
  if (status === "loading") {
    return (
      <StyledLoadingContainer>
        <Spinner animation="border" className="mx-auto" />
      </StyledLoadingContainer>
    )
  }

  if (status === "empty") {
    return <NoResults>{t("zero_results")}</NoResults>
  }

  return <Hits hitComponent={HearingHitComponent} />
}

const useHearingSort = () => {
  const { t } = useTranslation("search")

  return useMemo<SortByWithConfigurationItem[]>(
    () => [
      {
        label: t("sort_by.earliest_hearing"),
        value: "hearings/sort/startsAt:asc"
      },
      {
        label: t("sort_by.latest_hearing"),
        value: "hearings/sort/startsAt:desc"
      },
      {
        label: t("sort_by.relevance"),
        value: "hearings/sort/_text_match:desc,startsAt:asc"
      }
    ],
    [t]
  )
}

const useHearingRefinements = () => {
  const { t } = useTranslation("search")

  return useRefinements({
    refinementProps: useMemo(
      () =>
        [
          { attribute: "month" },
          { attribute: "year" },
          {
            attribute: "chairNames",
            transformItems: (items: RefinementListItem[]) =>
              items.sort((a, b) => a.label.localeCompare(b.label))
          }
        ].map(props => ({
          limit: 500,
          searchable: true,
          searchablePlaceholder: t(`refinements.hearing.${props.attribute}`),
          ...props
        })),
      [t]
    )
  })
}
