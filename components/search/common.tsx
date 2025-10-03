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

import { faFilter } from "@fortawesome/free-solid-svg-icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useCallback } from "react"
import { RefinementList, RefinementListProps } from "react-instantsearch"
import { useMediaQuery } from "usehooks-ts"
import { Button, Offcanvas } from "../bootstrap"
import {
  MultiselectHierarchicalMenu,
  MultiselectHierarchicalMenuParams
} from "./HierarchicalMenuWidget"
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

export const server = getServerConfig()

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
  filterPanelConfig,
  currentRefinementsProps = {},
  sortOptions,
  initialUiState,
  searchParameters
}: {
  searchType: SearchType
  header?: ReactNode
  filterPanelConfig: FilterPanelConfig
  currentRefinementsProps?: CurrentRefinementsProps
  leftColumnClassName?: string
  rightColumnClassName?: string
  hitComponent: ComponentType<{ hit: T }>
  sortOptions: SortOptionInput[]
  initialUiState?: any
  searchParameters: NonNullable<
    TypesenseInstantsearchAdapterOptions["additionalSearchParameters"]
  >
}) => {
  const { t } = useTranslation("search")
  const sortByItems = useMemo<SortByWithConfigurationItem[]>(
    () =>
      sortOptions.map(({ labelKey, ...opts }) => ({
        label: t(labelKey),
        ...opts
      })),
    [sortOptions, t]
  )
  const { filters, menuProps } = filterPanelConfig
  const filtersWithDefaults = useMemo(
    () =>
      filters.map(({ attribute, ...rest }) => ({
        attribute,
        ...defaultRefinementProps(attribute as string, searchType, t),
        ...rest
      })),
    [filters, searchType, t]
  )
  const menuAttributes = menuProps?.attributes ?? []
  const virtualFilters = useMemo(() => {
    const facets = new Set<string>()
    filtersWithDefaults.forEach(filter => facets.add(filter.attribute))
    menuAttributes.forEach(attr => (attr ? facets.add(attr) : null))
    return Array.from(facets)
  }, [filtersWithDefaults, menuAttributes])
  return (
    <SearchErrorBoundary>
      <InstantSearch
        indexName={sortByItems[0].value}
        initialUiState={initialUiState}
        searchClient={useMemo(
          () =>
            new TypesenseInstantSearchAdapter({
              server,
              additionalSearchParameters: searchParameters
            }).searchClient,
          [searchParameters]
        )}
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
        <VirtualFilters attributes={virtualFilters} />
        {header}
        <FilterPanel menuProps={menuProps} filters={filtersWithDefaults}>
          {({ filterPanel, filterToggle }) => (
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
                <Col xs={12} lg={3} className="mb-3 mb-lg-0">
                  {filterPanel}
                </Col>
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
          )}
        </FilterPanel>
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

export const FilterButton = styled(Button)`
  font-size: 1rem;
  line-height: 1rem;
  min-height: 2rem;
  padding: 0.25rem 0.5rem 0.25rem 0.5rem;
  align-self: flex-start;
`

type MobilePanelProps = {
  title: string
  isOpen: boolean
  onClose: () => void
  menu: ReactNode | null
  refinementLists: ReactNode[]
}

const MobileFilterPanel = ({
  title,
  isOpen,
  onClose,
  menu,
  refinementLists
}: MobilePanelProps) => (
  <Offcanvas show={isOpen} onHide={onClose} placement="start">
    <Offcanvas.Header closeButton>
      <Offcanvas.Title>{title}</Offcanvas.Title>
    </Offcanvas.Header>
    <Offcanvas.Body>
      {menu ? <SearchContainer>{menu}</SearchContainer> : null}
      {refinementLists.length ? (
        <SearchContainer>{refinementLists}</SearchContainer>
      ) : null}
    </Offcanvas.Body>
  </Offcanvas>
)

export type FilterPanelConfig = {
  filters: RefinementListProps[]
  menuProps?: MultiselectHierarchicalMenuParams
}

const createMobileFilterElements = ({
  title,
  isOpen,
  hasRefinements,
  onOpen,
  onClose,
  menu,
  refinementLists
}: MobilePanelProps & {
  hasRefinements: boolean
  onOpen: () => void
}) => {
  return {
    filterPanel: (
      <MobileFilterPanel
        title={title}
        isOpen={isOpen}
        onClose={onClose}
        menu={menu}
        refinementLists={refinementLists}
      />
    ),
    filterToggle: (
      <FilterButton
        variant="secondary"
        active={isOpen}
        onClick={onOpen}
        className={hasRefinements ? "ais-FilterButton-has-refinements" : ""}
      >
        <FontAwesomeIcon icon={faFilter} /> {title}
      </FilterButton>
    )
  }
}

const createDesktopFilterElements = ({
  menu,
  refinementLists
}: {
  menu: ReactNode | null
  refinementLists: ReactNode[]
}) => {
  return {
    filterPanel: (
      <>
        {menu ? <div>{menu}</div> : null}
        {refinementLists.length ? <div>{refinementLists}</div> : null}
      </>
    ),
    filterToggle: null
  }
}

const useHasRefinements = () => {
  return useInstantSearch().results.getRefinements().length > 0
}

export const FilterPanel = ({
  menuProps,
  filters,
  children
}: FilterPanelConfig & {
  children: (result: {
    filterPanel: ReactNode
    filterToggle: ReactNode | null
  }) => ReactNode
}) => {
  const isDesktop = useMediaQuery("(min-width: 768px)")
  const hasRefinements = useHasRefinements()
  const [isOpen, setIsOpen] = useState(false)
  const menu = useMemo(
    () => (menuProps ? <MultiselectHierarchicalMenu {...menuProps} /> : null),
    [menuProps]
  )
  const refinementLists = useMemo(
    () =>
      filters.map(props => (
        <RefinementList className="mb-4" key={props.attribute} {...props} />
      )),
    [filters]
  )
  const openMobilePanel = useCallback(() => setIsOpen(true), [])
  const closeMobilePanel = useCallback(() => setIsOpen(false), [])
  const { t } = useTranslation("search")
  const { filterPanel, filterToggle } = isDesktop
    ? createDesktopFilterElements({ menu, refinementLists })
    : createMobileFilterElements({
        title: t("filter"),
        isOpen,
        hasRefinements,
        onOpen: openMobilePanel,
        onClose: closeMobilePanel,
        menu,
        refinementLists
      })

  return <>{children({ filterPanel, filterToggle })}</>
}

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
