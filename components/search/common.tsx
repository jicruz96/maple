import { Hit } from "instantsearch.js"
import { TFunction, useTranslation } from "next-i18next"
import singletonRouter from "next/router"
import { ComponentType, ReactNode, useMemo, useState } from "react"
import {
  CurrentRefinements,
  CurrentRefinementsProps,
  Hits,
  InstantSearch,
  Pagination,
  SearchBox,
  useInstantSearch,
  useRefinementList
} from "react-instantsearch"
import { createInstantSearchRouterNext } from "react-instantsearch-router-nextjs"
import styled from "styled-components"
import TypesenseInstantSearchAdapter, {
  TypesenseInstantsearchAdapterOptions
} from "typesense-instantsearch-adapter"
import { Col, Container, Row, Spinner } from "../bootstrap"
import { ResultCount } from "./ResultCount"
import { pathToSearchState, searchStateToUrl } from "./routingHelpers"
import { SearchContainer } from "./SearchContainer"
import { SortBy, SortByWithConfigurationItem } from "./SortBy"
import { useFilterPanel, FilterPanelConfig } from "./useFilterPanel"

import { NoResults } from "./NoResults"
import { SearchErrorBoundary } from "./SearchErrorBoundary"

const devConfig = {
  key: "Wk0K3oMIE1ERRmwX0uLgEk3gGEGKNuQe",
  // key: "mfylP3FhQBBAmUiDTWZ9PNbhzTtVID1W",
  url: "https://o89yhjf824.execute-api.us-east-1.amazonaws.com/search"
}

export function getServerConfig(): TypesenseInstantsearchAdapterOptions["server"] {
  const key = process.env.NEXT_PUBLIC_TYPESENSE_SEARCH_API_KEY ?? devConfig.key
  const url = new URL(
    process.env.NEXT_PUBLIC_TYPESENSE_API_URL ?? devConfig.url
  )

  const protocol = url.protocol.startsWith("https") ? "https" : "http"
  const port = url.port ? Number(url.port) : protocol === "https" ? 443 : 80

  return {
    apiKey: key,
    nodes: [
      {
        host: url.hostname,
        protocol,
        port,
        path: url.pathname
      }
    ]
  }
}

const VirtualRefinementWidget = ({ attribute }: { attribute: string }) => {
  useRefinementList({ attribute, limit: 500 })
  return null
}

export const VirtualFilters = ({ attributes }: { attributes: string[] }) => (
  <>
    {attributes.map(attribute => (
      <VirtualRefinementWidget key={attribute} attribute={attribute} />
    ))}
  </>
)

export type SearchStatus = "loading" | "empty" | "results"

export const useSearchStatus = (): SearchStatus => {
  const { results } = useInstantSearch()
  if (!results.query) return "loading"
  if (results.nbHits === 0) return "empty"
  return "results"
}

export const RefinementToolbar = styled.div`
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
`

export type SearchType = "bill" | "testimony" | "hearing"

const defaultRefinementProps = (
  attribute: string,
  searchType: SearchType,
  t: TFunction
) => ({
  limit: 500,
  searchable: true,
  searchablePlaceholder: t(`refinements.${searchType}.${attribute}`)
})

export type SortOptionInput = {
  labelKey: string
  value: string
  configure?: SortByWithConfigurationItem["configure"]
}

export const SearchPage = <T extends Hit>({
  searchType,
  header,
  hitComponent,
  filterConfig,
  currentRefinementsProps = {},
  sortOptions,
  virtualFacetAttributes,
  initialUiState,
  searchParameters
}: {
  searchType: SearchType
  header?: ReactNode
  filterConfig: FilterPanelConfig
  currentRefinementsProps?: CurrentRefinementsProps
  leftColumnClassName?: string
  rightColumnClassName?: string
  hitComponent: ComponentType<{ hit: T }>
  sortOptions: SortOptionInput[]
  virtualFacetAttributes: string[]
  initialUiState?: any
  searchParameters: NonNullable<
    TypesenseInstantsearchAdapterOptions["additionalSearchParameters"]
  >
}) => {
  const { t } = useTranslation("search")
  const searchClient = useMemo(
    () =>
      new TypesenseInstantSearchAdapter({
        server: getServerConfig(),
        additionalSearchParameters: searchParameters
      }).searchClient,
    [searchParameters]
  )
  const sortByItems = useMemo<SortByWithConfigurationItem[]>(() => {
    return sortOptions.map(({ labelKey, ...rest }) => ({
      label: t(labelKey),
      ...rest
    }))
  }, [sortOptions, t])

  const { filters, hierarchicalMenu } = filterConfig

  const { panel: filterPanel, toggle: filterToggle } = useFilterPanel({
    hierarchicalMenu,
    filters: useMemo(
      () =>
        filters.map(({ attribute, ...rest }) => ({
          attribute,
          ...defaultRefinementProps(attribute as string, searchType, t),
          ...rest
        })),
      [filters, searchType, t]
    )
  })
  const shouldRenderFilterColumn = Boolean(filterPanel)
  return (
    <SearchErrorBoundary>
      <InstantSearch
        indexName={sortByItems[0].value}
        searchClient={searchClient}
        initialUiState={initialUiState}
        routing={{
          router: createInstantSearchRouterNext({
            singletonRouter,
            routerOptions: {
              cleanUrlOnDispose: false,
              createURL: searchStateToUrl,
              parseURL: pathToSearchState
            }
          })
        }}
        future={{ preserveSharedStateOnUnmount: true }}
      >
        <VirtualFilters attributes={virtualFacetAttributes} />
        {header}
        <SearchContainer>
          <Row>
            <Col xs={12}>
              <SearchBox
                placeholder={t(`search_box.placeholder.${searchType}`)}
                className="mt-2 mb-3"
              />
            </Col>
          </Row>
          <Row>
            {shouldRenderFilterColumn && (
              <Col xs={12} lg={3} className="mb-3 mb-lg-0">
                {filterPanel}
              </Col>
            )}
            <Col className="d-flex flex-column">
              <RefinementToolbar>
                <ResultCount className="flex-grow-1 m-1" />
                <SortBy items={sortByItems} />
                {filterToggle}
              </RefinementToolbar>
              <CurrentRefinements
                className="mt-2 mb-2"
                {...currentRefinementsProps}
              />
              <SearchResults hitComponent={hitComponent} />
              <Pagination className="mx-auto mt-2 mb-3" />
            </Col>
          </Row>
        </SearchContainer>
      </InstantSearch>
    </SearchErrorBoundary>
  )
}

const StyledLoadingContainer = styled(Container)`
  background-color: white;
  display: flex;
  height: 300px;
  justify-content: center;
  align-items: center;
`

const SearchResults = <TRecord extends Hit>({
  hitComponent
}: {
  hitComponent: ComponentType<{ hit: TRecord }>
}) => {
  const { t } = useTranslation("search")
  const status = useSearchStatus()
  const [isNavigating, setIsNavigating] = useState(false)

  if (status === "loading" || isNavigating) {
    return (
      <StyledLoadingContainer>
        <Spinner animation="border" className="mx-auto" />
      </StyledLoadingContainer>
    )
  }

  if (status === "empty") {
    return (
      <NoResults>
        {t("zero_results")}
        <br />
        <b>{t("another_term")}</b>
      </NoResults>
    )
  }

  return (
    <Hits hitComponent={hitComponent} onClick={() => setIsNavigating(true)} />
  )
}
