import { useRefinementList } from "react-instantsearch"

type VirtualRefinementWidgetProps = {
  attribute: string
}

const VirtualRefinementWidget = ({
  attribute
}: VirtualRefinementWidgetProps) => {
  useRefinementList({ attribute, limit: 500 })
  return null
}

export type VirtualFiltersProps = {
  attributes: string[]
}

export const VirtualFilters = ({ attributes }: VirtualFiltersProps) => (
  <>
    {attributes.map(attribute => (
      <VirtualRefinementWidget key={attribute} attribute={attribute} />
    ))}
  </>
)
