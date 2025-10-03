import { faFilter } from "@fortawesome/free-solid-svg-icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { useTranslation } from "next-i18next"
import {
  RefinementList,
  RefinementListProps,
  useInstantSearch
} from "react-instantsearch"
import { ReactNode, useCallback, useMemo, useState } from "react"
import styled from "styled-components"
import { useMediaQuery } from "usehooks-ts"
import { Button, Offcanvas } from "../bootstrap"
import {
  MultiselectHierarchicalMenu,
  MultiselectHierarchicalMenuParams
} from "./HierarchicalMenuWidget"
import { SearchContainer } from "./SearchContainer"

export const FilterButton = styled(Button)`
  font-size: 1rem;
  line-height: 1rem;
  min-height: 2rem;
  padding: 0.25rem 0.5rem 0.25rem 0.5rem;
  align-self: flex-start;
`

export type FilterPanelConfig = {
  hierarchicalMenu?: MultiselectHierarchicalMenuParams
  filters: RefinementListProps[]
}

export type FilterPanelResult = {
  panel: ReactNode
  toggle: ReactNode | null
}

const useHasRefinements = () => {
  return useInstantSearch().results.getRefinements().length !== 0
}

export const useFilterPanel = ({
  hierarchicalMenu,
  filters
}: FilterPanelConfig): FilterPanelResult => {
  const isDesktop = useMediaQuery("(min-width: 768px)")
  const hasRefinements = useHasRefinements()
  const [isOpen, setIsOpen] = useState(false)
  const hierarchicalWidget = useMemo(
    () =>
      hierarchicalMenu ? (
        <MultiselectHierarchicalMenu {...hierarchicalMenu} />
      ) : null,
    [hierarchicalMenu]
  )
  const refinementLists = useMemo(
    () =>
      filters.map((props, index) => (
        <RefinementList
          className="mb-4"
          key={props.attribute ?? String(index)}
          {...props}
        />
      )),
    [filters]
  )
  const openMobilePanel = useCallback(() => setIsOpen(true), [])
  const closeMobilePanel = useCallback(() => setIsOpen(false), [])

  const { t } = useTranslation("search")

  if (isDesktop) {
    return {
      panel: (
        <>
          {hierarchicalWidget ? <div>{hierarchicalWidget}</div> : null}
          {refinementLists.length ? <div>{refinementLists}</div> : null}
        </>
      ),
      toggle: null
    }
  }

  return {
    panel: (
      <Offcanvas show={isOpen} onHide={closeMobilePanel} placement="start">
        <Offcanvas.Header closeButton>
          <Offcanvas.Title>{t("filter")}</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body>
          {hierarchicalWidget ? (
            <SearchContainer>{hierarchicalWidget}</SearchContainer>
          ) : null}
          {refinementLists.length ? (
            <SearchContainer>{refinementLists}</SearchContainer>
          ) : null}
        </Offcanvas.Body>
      </Offcanvas>
    ),
    toggle: (
      <FilterButton
        variant="secondary"
        active={isOpen}
        onClick={openMobilePanel}
        className={hasRefinements ? "ais-FilterButton-has-refinements" : ""}
      >
        <FontAwesomeIcon icon={faFilter} /> {t("filter")}
      </FilterButton>
    )
  }
}
