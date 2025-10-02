import { useMemo } from "react"
import { RefinementListItem } from "instantsearch.js/es/connectors/refinement-list/connectRefinementList"
import { useTranslation } from "next-i18next"
import { useRefinements } from "../useRefinements"

export const useHearingRefinements = () => {
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
